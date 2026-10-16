"""StripeGateway against a recording stand-in for the Stripe client. Real test-mode run is documented in docs/results.md."""

from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.executor import Executor
from app.gateway import GatewayError, StripeGateway, gateway_from_env
from app.models import GatewayLedger
from app.policy_engine import Decision, Outcome
from app.repository import find_order
from app.signing import sign_decision


class RecordingStripe:
    def __init__(self):
        self.calls = []
        self.v1 = SimpleNamespace(refunds=SimpleNamespace(create=self._create))

    def _create(self, params, options=None):
        self.calls.append((params, options))
        return SimpleNamespace(id=f"re_test_{len(self.calls)}", amount=params["amount"])


@pytest.mark.parametrize("key", ["sk_live_abc", "rk_live_abc"])
def test_live_keys_refused(key):
    with pytest.raises(GatewayError, match="LIVE"):
        StripeGateway(key, client=RecordingStripe())


def test_non_test_key_refused_without_mock_base():
    with pytest.raises(GatewayError, match="sk_test_"):
        StripeGateway("pk_test_abc", client=RecordingStripe())


def test_app_refuses_to_start_on_live_key(monkeypatch):
    monkeypatch.setenv("PAYMENT_GATEWAY", "stripe")
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_live_abc")
    with pytest.raises(GatewayError, match="LIVE"):
        gateway_from_env()


def test_executor_refunds_payment_intent_with_decision_id_as_idempotency_key(sessions, frozen_now):
    stripe = RecordingStripe()
    gw = StripeGateway("sk_test_abc", client=stripe)
    with sessions() as s:
        order = find_order(s, "HM-1005")
        order.gateway_payment_ref = "pi_test_123"
        s.commit()
        d = Decision(Outcome.APPROVE, order.id, (order.items[0].id,), ("R2",), "ok", amount_cents=7_900)
    result = Executor(sessions, gw, b"k").execute(sign_decision(d, b"k", frozen_now))
    [(params, options)] = stripe.calls
    assert params["payment_intent"] == "pi_test_123" and params["amount"] == 7_900
    assert options == {"idempotency_key": result.decision_id}
    with sessions() as s:
        [row] = s.scalars(select(GatewayLedger)).all()
        assert (row.gateway, row.gateway_ref, row.amount_cents) == ("stripe", "re_test_1", 7_900)


def test_order_without_stripe_payment_is_not_refunded(sessions, frozen_now):
    stripe = RecordingStripe()
    with sessions() as s:
        order = find_order(s, "HM-1005")
        d = Decision(Outcome.APPROVE, order.id, (order.items[0].id,), ("R2",), "ok", amount_cents=7_900)
    with pytest.raises(GatewayError):
        Executor(sessions, StripeGateway("sk_test_abc", client=stripe), b"k").execute(
            sign_decision(d, b"k", frozen_now))
    assert stripe.calls == []
