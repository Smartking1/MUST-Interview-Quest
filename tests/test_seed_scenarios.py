"""Each seeded order produces the outcome its seed comment promises."""

import pytest

from app.policy_engine import (
    Outcome,
    ReasonCode,
    ReceivedReturn,
    evaluate_address_change,
    evaluate_received_returns,
    evaluate_request,
)
from app.repository import find_order, order_snapshot, refund_history

R = ReasonCode


def decide(sessions, number, reason, now, items=None):
    with sessions() as s:
        order = find_order(s, number)
        snap = order_snapshot(order)
        ids = tuple(items) if items is not None else tuple(i.line_item_id for i in snap.items)
        return evaluate_request(snap, ids, reason, refund_history(s, order.customer_id), now)


@pytest.mark.parametrize("number,reason,expected,rules", [
    ("HM-1001", R.CANCEL_UNSHIPPED, Outcome.APPROVE, {"R1"}),
    ("HM-1002", R.CANCEL_UNSHIPPED, Outcome.ESCALATE, {"R8"}),
    ("HM-1003", R.CANCEL_UNSHIPPED, Outcome.DENY, {"R1"}),
    ("HM-1005", R.RETURN, Outcome.RETURN_AUTHORIZED, {"R2"}),
    ("HM-1006", R.RETURN, Outcome.RETURN_AUTHORIZED, {"R2"}),
    ("HM-1007", R.RETURN, Outcome.DENY, {"R2"}),
    ("HM-1011", R.DEFECTIVE, Outcome.ESCALATE, {"R4"}),
    ("HM-1012", R.DEFECTIVE, Outcome.DENY, {"R4"}),
    ("HM-1013", R.DAMAGED_IN_DELIVERY, Outcome.ESCALATE, {"R5"}),
    ("HM-1014", R.DAMAGED_IN_DELIVERY, Outcome.DENY, {"R5"}),
    ("HM-1015", R.RETURN, Outcome.DENY, {"R6"}),
    ("HM-1017", R.RETURN, Outcome.DENY, {"R7"}),
])
def test_seeded_order_outcomes(sessions, frozen_now, number, reason, expected, rules):
    d = decide(sessions, number, reason, frozen_now)
    assert d.outcome == expected
    assert rules <= set(d.rule_ids)


def test_mixed_final_sale_order_authorizes_only_returnable_item(sessions, frozen_now):
    d = decide(sessions, "HM-1016", R.RETURN, frozen_now)
    assert d.outcome == Outcome.RETURN_AUTHORIZED
    assert len(d.line_item_ids) == 1


def receive_all(sessions, number, now, opened=False, tags=False, requested_days_after=1):
    with sessions() as s:
        order = find_order(s, number)
        snap = order_snapshot(order)
        from datetime import timedelta
        rets = tuple(ReceivedReturn(i.line_item_id, snap.delivered_at + timedelta(days=requested_days_after),
                                    opened, tags) for i in snap.items)
        return evaluate_received_returns(snap, rets, refund_history(s, order.customer_id), now)


def test_hm1008_opened_return_pays_less_restocking_fee(sessions, frozen_now):
    assert receive_all(sessions, "HM-1008", frozen_now, opened=True).amount_cents == 10_200


def test_hm1009_fashion_with_tags_pays_in_full(sessions, frozen_now):
    assert receive_all(sessions, "HM-1009", frozen_now, opened=True, tags=True).amount_cents == 18_500


def test_hm1010_opened_after_15_days_denied(sessions, frozen_now):
    d = receive_all(sessions, "HM-1010", frozen_now, opened=True, requested_days_after=20)
    assert d.outcome == Outcome.DENY


def test_hm1018_discounted_order_capped_at_paid(sessions, frozen_now):
    d = receive_all(sessions, "HM-1018", frozen_now)
    assert d.amount_cents == 11_000 + 499 - 3_000


def test_hm1019_whole_order_return_escalates_r8(sessions, frozen_now):
    assert receive_all(sessions, "HM-1019", frozen_now).outcome == Outcome.ESCALATE


def test_hm1020_laptop_escalates_r8(sessions, frozen_now):
    assert receive_all(sessions, "HM-1020", frozen_now).outcome == Outcome.ESCALATE


def test_hm1021_exactly_200_auto_approves(sessions, frozen_now):
    d = receive_all(sessions, "HM-1021", frozen_now)
    assert d.outcome == Outcome.APPROVE
    assert d.amount_cents == 20_000


def test_hm1024_third_refund_in_90_days_escalates_r9(sessions, frozen_now):
    d = receive_all(sessions, "HM-1024", frozen_now)
    assert d.outcome == Outcome.ESCALATE
    assert "R9" in d.rule_ids


@pytest.mark.parametrize("number,expected", [("HM-1004", Outcome.APPROVE), ("HM-1003", Outcome.DENY)])
def test_address_change_scenarios(sessions, number, expected):
    with sessions() as s:
        assert evaluate_address_change(order_snapshot(find_order(s, number))).outcome == expected
