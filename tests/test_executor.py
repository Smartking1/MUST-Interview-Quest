from dataclasses import replace
from datetime import timedelta

import pytest
from sqlalchemy import func, select

from app.executor import ExecutionRejected, Executor
from app.gateway import FakeGateway
from app.models import GatewayLedger, Order, Refund
from app.policy_engine import Decision, Outcome
from app.repository import find_order
from app.signing import sign_decision

SECRET = b"executor-test-secret"


@pytest.fixture
def executor(sessions):
    return Executor(sessions, FakeGateway(), SECRET)


def approved(sessions, number, amount, rules=("R2",)):
    with sessions() as s:
        o = find_order(s, number)
        return Decision(Outcome.APPROVE, o.id, tuple(i.id for i in o.items), rules, "ok",
                        amount_cents=amount)


def ledger_total(sessions):
    with sessions() as s:
        return s.scalar(select(func.coalesce(func.sum(GatewayLedger.amount_cents), 0)))


def test_valid_decision_pays_once_and_records_refund(sessions, executor, frozen_now):
    token = sign_decision(approved(sessions, "HM-1005", 7_900), SECRET, frozen_now)
    result = executor.execute(token)
    assert result.amount_cents == 7_900
    assert ledger_total(sessions) == 7_900
    with sessions() as s:
        assert s.scalar(select(Refund).where(Refund.decision_id == result.decision_id)).gateway_ref


def test_replayed_decision_is_rejected_and_pays_nothing_more(sessions, executor, frozen_now):
    """A partial refund leaves room under R7, so only the replay check can stop the second payout."""
    with sessions() as s:
        o = find_order(s, "HM-1019")
        first_item = (o.items[0].id,)
    d = Decision(Outcome.APPROVE, o.id, first_item, ("R2",), "ok", amount_cents=5_000)
    token = sign_decision(d, SECRET, frozen_now)
    executor.execute(token)
    with pytest.raises(ExecutionRejected, match="already been used"):
        executor.execute(token)
    assert ledger_total(sessions) == 5_000


def test_forged_signature_is_rejected(sessions, executor, frozen_now):
    token = sign_decision(approved(sessions, "HM-1005", 7_900), b"attacker-secret", frozen_now)
    with pytest.raises(ExecutionRejected):
        executor.execute(token)
    assert ledger_total(sessions) == 0


def test_expired_decision_is_rejected(sessions, executor, frozen_now):
    token = sign_decision(approved(sessions, "HM-1005", 7_900), SECRET, frozen_now - timedelta(hours=1))
    with pytest.raises(ExecutionRejected, match="expired"):
        executor.execute(token)


def test_executor_rechecks_r7_against_live_database(sessions, executor, frozen_now):
    """Even a validly signed decision cannot pay more than the order's remaining balance."""
    token = sign_decision(approved(sessions, "HM-1005", 1_000_000), SECRET, frozen_now)
    with pytest.raises(ExecutionRejected, match="R7"):
        executor.execute(token)
    assert ledger_total(sessions) == 0


def test_two_valid_decisions_for_the_same_item_pay_once(sessions, executor, frozen_now):
    d = approved(sessions, "HM-1016", 3_000)
    executor.execute(sign_decision(d, SECRET, frozen_now))
    with pytest.raises(ExecutionRejected, match="already been refunded"):
        executor.execute(sign_decision(d, SECRET, frozen_now))
    assert ledger_total(sessions) == 3_000


def test_items_from_another_order_are_rejected(sessions, executor, frozen_now):
    d = approved(sessions, "HM-1005", 1_000)
    other = approved(sessions, "HM-1025", 1_000)
    with pytest.raises(ExecutionRejected, match="not on this order"):
        executor.execute(sign_decision(replace(d, line_item_ids=other.line_item_ids), SECRET, frozen_now))


def test_r1_execution_cancels_the_order(sessions, executor, frozen_now):
    executor.execute(sign_decision(approved(sessions, "HM-1001", 5_098, ("R1",)), SECRET, frozen_now))
    with sessions() as s:
        assert find_order(s, "HM-1001").status == "cancelled"


def test_gateway_failure_rolls_back_the_refund_record(sessions, frozen_now):
    class BrokenGateway(FakeGateway):
        def refund(self, *a, **k):
            raise RuntimeError("gateway down")

    ex = Executor(sessions, BrokenGateway(), SECRET)
    token = sign_decision(approved(sessions, "HM-1005", 7_900), SECRET, frozen_now)
    with pytest.raises(RuntimeError):
        ex.execute(token)
    with sessions() as s:
        assert s.scalar(select(func.count()).select_from(Refund).where(Refund.issuer != "seed")) == 0
    # The same decision can be retried once the gateway is back
    assert Executor(sessions, FakeGateway(), SECRET).execute(token).amount_cents == 7_900
