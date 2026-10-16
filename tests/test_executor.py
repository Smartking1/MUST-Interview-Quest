from dataclasses import replace
from datetime import timedelta

import pytest
from sqlalchemy import func, select

from app.executor import ExecutionRejected, Executor
from app.gateway import FakeGateway, GatewayRejected
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
                        amount_kobo=amount)


def ledger_total(sessions):
    with sessions() as s:
        return s.scalar(select(func.coalesce(func.sum(GatewayLedger.amount_kobo), 0)))


def test_valid_decision_pays_once_and_records_refund(sessions, executor, frozen_now):
    token = sign_decision(approved(sessions, "HM-1005", 7_900), SECRET, frozen_now)
    result = executor.execute(token)
    assert result.amount_kobo == 7_900
    assert ledger_total(sessions) == 7_900
    with sessions() as s:
        assert s.scalar(select(Refund).where(Refund.decision_id == result.decision_id)).gateway_ref


def test_replayed_decision_is_rejected_and_pays_nothing_more(sessions, executor, frozen_now):
    """A partial refund leaves room under R7, so only the replay check can stop the second payout."""
    with sessions() as s:
        o = find_order(s, "HM-1019")
        first_item = (o.items[0].id,)
    d = Decision(Outcome.APPROVE, o.id, first_item, ("R2",), "ok", amount_kobo=5_000)
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
    token = sign_decision(approved(sessions, "HM-1005", 100_000_000), SECRET, frozen_now)
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


def test_gateway_rejection_is_recorded_and_the_decision_cannot_be_replayed(sessions, frozen_now):
    class RejectingGateway(FakeGateway):
        def refund(self, *a, **k):
            raise GatewayRejected("card network said no")

    token = sign_decision(approved(sessions, "HM-1005", 7_900), SECRET, frozen_now)
    with pytest.raises(GatewayRejected):
        Executor(sessions, RejectingGateway(), SECRET).execute(token)
    with sessions() as s:
        [r] = s.scalars(select(Refund).where(Refund.issuer != "seed")).all()
        assert r.status == "failed"
    assert ledger_total(sessions) == 0
    # The same token is spent; a fresh policy decision is needed, and a failed refund does not block it
    with pytest.raises(ExecutionRejected, match="already been used"):
        Executor(sessions, FakeGateway(), SECRET).execute(token)
    fresh = sign_decision(approved(sessions, "HM-1005", 7_900), SECRET, frozen_now)
    assert Executor(sessions, FakeGateway(), SECRET).execute(fresh).amount_kobo == 7_900


def test_crash_after_gateway_pays_leaves_pending_refund_that_blocks_a_second_payout(sessions, frozen_now):
    """Paystack refunds are not idempotent. If we die after paying but before recording, never pay again."""
    class CrashAfterPaying(Executor):
        def _finish(self, *a, **k):
            raise SystemExit("process killed")

    with pytest.raises(SystemExit):
        CrashAfterPaying(sessions, FakeGateway(), SECRET).execute(
            sign_decision(approved(sessions, "HM-1005", 7_900), SECRET, frozen_now))
    assert ledger_total(sessions) == 7_900
    with sessions() as s:
        [r] = s.scalars(select(Refund).where(Refund.issuer != "seed")).all()
        assert r.status == "pending"
    with pytest.raises(ExecutionRejected, match="R7"):
        Executor(sessions, FakeGateway(), SECRET).execute(
            sign_decision(approved(sessions, "HM-1005", 7_900), SECRET, frozen_now))
    assert ledger_total(sessions) == 7_900


def test_gateway_timeout_leaves_refund_pending_and_blocks_retry(sessions, frozen_now):
    """A timeout might have paid. Never treat it as a failure that frees the money for another try."""
    class TimeoutGateway(FakeGateway):
        def refund(self, *a, **k):
            raise TimeoutError("no response")

    with pytest.raises(TimeoutError):
        Executor(sessions, TimeoutGateway(), SECRET).execute(
            sign_decision(approved(sessions, "HM-1005", 7_900), SECRET, frozen_now))
    with sessions() as s:
        [r] = s.scalars(select(Refund).where(Refund.issuer != "seed")).all()
        assert r.status == "pending"
    with pytest.raises(ExecutionRejected, match="R7"):
        Executor(sessions, FakeGateway(), SECRET).execute(
            sign_decision(approved(sessions, "HM-1005", 7_900), SECRET, frozen_now))
