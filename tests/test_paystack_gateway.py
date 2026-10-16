"""PaystackGateway over httpx.MockTransport: checks exactly what is sent and how each response is handled.

The real test-mode refund is recorded in docs/results.md.
"""

import json

import httpx
import pytest
from sqlalchemy import select

from app.executor import Executor
from app.gateway import GatewayError, GatewayRejected, PaystackGateway, gateway_from_env
from app.models import GatewayLedger, Refund
from app.policy_engine import Decision, Outcome
from app.repository import find_order
from app.signing import sign_decision


def gateway(handler, calls):
    def record(request):
        calls.append(request)
        return handler(request)

    client = httpx.Client(base_url="https://api.paystack.co", transport=httpx.MockTransport(record),
                          headers={"Authorization": "Bearer sk_test_abc"})
    return PaystackGateway("sk_test_abc", client=client)


def ok(request):
    return httpx.Response(200, json={"status": True, "message": "Refund has been queued for processing",
                                     "data": {"id": 3018284, "status": "pending", "amount": 7900}})


def decision(sessions, frozen_now, ref="T685312322670591"):
    with sessions() as s:
        order = find_order(s, "HM-1005")
        order.gateway_payment_ref = ref
        s.commit()
        d = Decision(Outcome.APPROVE, order.id, (order.items[0].id,), ("R2",), "ok", amount_kobo=7_900)
    return sign_decision(d, b"k", frozen_now)


@pytest.mark.parametrize("key,msg", [("sk_live_abc", "LIVE"), ("pk_test_abc", "sk_test_"), ("", "No payment")])
def test_only_secret_test_keys_accepted(key, msg):
    with pytest.raises(GatewayError, match=msg):
        PaystackGateway(key)


def test_app_refuses_to_start_on_live_key(monkeypatch):
    monkeypatch.setenv("PAYMENT_GATEWAY", "paystack")
    monkeypatch.setenv("PAYSTACK_SECRET_KEY", "sk_live_abc")
    with pytest.raises(GatewayError, match="LIVE"):
        gateway_from_env()


def test_refund_request_shape_and_ledger(sessions, frozen_now):
    calls = []
    result = Executor(sessions, gateway(ok, calls), b"k").execute(decision(sessions, frozen_now))
    [req] = calls
    body = json.loads(req.content)
    assert req.url.path == "/refund" and req.headers["Authorization"] == "Bearer sk_test_abc"
    assert body["transaction"] == "T685312322670591"
    assert body["amount"] == 7_900 and body["currency"] == "NGN"
    assert result.decision_id in body["merchant_note"]
    with sessions() as s:
        [row] = s.scalars(select(GatewayLedger)).all()
        assert (row.gateway, row.gateway_ref) == ("paystack", "paystack_refund_3018284")
        assert s.scalar(select(Refund).where(Refund.decision_id == result.decision_id)).status == "succeeded"


def test_paystack_4xx_is_a_definite_failure(sessions, frozen_now):
    calls = []
    reject = lambda r: httpx.Response(400, json={"status": False, "message": "Transaction has been fully reversed"})
    with pytest.raises(GatewayRejected, match="fully reversed"):
        Executor(sessions, gateway(reject, calls), b"k").execute(decision(sessions, frozen_now))
    with sessions() as s:
        assert s.scalar(select(Refund).where(Refund.issuer != "seed")).status == "failed"


def test_paystack_5xx_leaves_refund_pending(sessions, frozen_now):
    calls = []
    with pytest.raises(httpx.HTTPStatusError):
        Executor(sessions, gateway(lambda r: httpx.Response(502), calls), b"k").execute(
            decision(sessions, frozen_now))
    with sessions() as s:
        assert s.scalar(select(Refund).where(Refund.issuer != "seed")).status == "pending"


def test_order_without_paystack_payment_is_not_sent(sessions, frozen_now):
    calls = []
    with pytest.raises(GatewayRejected):
        Executor(sessions, gateway(ok, calls), b"k").execute(decision(sessions, frozen_now, ref=None))
    assert calls == []
