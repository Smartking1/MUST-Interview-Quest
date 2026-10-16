from datetime import UTC, datetime, timedelta

import pytest

from app.policy_engine import (
    AUTO_APPROVAL_LIMIT_KOBO as LIMIT,
    Decision,
    ItemSnapshot,
    OrderSnapshot,
    OrderStatus,
    Outcome,
    ReasonCode,
    ReceivedReturn,
    RefundRecord,
    evaluate_address_change,
    evaluate_cancellation,
    evaluate_received_returns,
    evaluate_request,
    identity_matches,
    restocking_fee_kobo,
)

NOW = datetime(2026, 10, 15, 12, 0, tzinfo=UTC)


def item(line_item_id=1, price=5_000, category="electronics", qty=1, final_sale=False):
    return ItemSnapshot(line_item_id, category, price, qty, final_sale)


def order(*items, status=OrderStatus.DELIVERED, days_since_delivery=5, paid=None, order_id=100):
    items = items or (item(),)
    return OrderSnapshot(
        order_id=order_id,
        customer_id=1,
        status=status,
        paid_kobo=paid if paid is not None else sum(i.total_kobo for i in items),
        items=tuple(items),
        delivered_at=NOW - timedelta(days=days_since_delivery) if status == OrderStatus.DELIVERED else None,
    )


def refund(amount, days_ago, order_id=999, line_item_ids=()):
    return RefundRecord(order_id, amount, NOW - timedelta(days=days_ago), line_item_ids)


def received(o, line_item_id=1, days_after_delivery=5, opened=False, tags=False):
    return ReceivedReturn(line_item_id, o.delivered_at + timedelta(days=days_after_delivery), opened, tags)


def receive(o, *rets, history=()):
    return evaluate_received_returns(o, tuple(rets), tuple(history), NOW)


def request(o, ids=(1,), reason=ReasonCode.RETURN, history=()):
    return evaluate_request(o, tuple(ids), reason, tuple(history), NOW)


# ------------------------------------------------------------------ R1


def test_r1_unshipped_order_cancels_for_full_paid_amount():
    o = order(item(price=4_000), status=OrderStatus.PLACED, paid=4_599)  # paid includes shipping
    d = evaluate_cancellation(o, (), NOW)
    assert d.outcome == Outcome.APPROVE
    assert d.amount_kobo == 4_599
    assert d.rule_ids == ("R1",)


@pytest.mark.parametrize("status", [OrderStatus.SHIPPED, OrderStatus.DELIVERED])
def test_r1_shipped_order_cannot_be_cancelled(status):
    d = evaluate_cancellation(order(status=status), (), NOW)
    assert d.outcome == Outcome.DENY
    assert d.amount_kobo == 0


def test_r1_cancelled_order_cannot_be_cancelled_again():
    d = evaluate_cancellation(order(status=OrderStatus.CANCELLED), (), NOW)
    assert d.outcome == Outcome.DENY


def test_r1_cancellation_reason_code_routes_to_cancellation():
    o = order(status=OrderStatus.PLACED)
    assert request(o, reason=ReasonCode.CANCEL_UNSHIPPED).outcome == Outcome.APPROVE


def test_r1_cancellation_over_limit_escalates_under_r8():
    d = evaluate_cancellation(order(item(price=LIMIT + 1), status=OrderStatus.PLACED), (), NOW)
    assert d.outcome == Outcome.ESCALATE
    assert "R8" in d.rule_ids
    assert d.amount_kobo == 0
    assert d.proposed_amount_kobo == LIMIT + 1


def test_return_request_on_unshipped_order_points_to_cancellation():
    d = request(order(status=OrderStatus.PLACED))
    assert d.outcome == Outcome.DENY
    assert d.rule_ids == ("R1",)


def test_shipped_not_delivered_escalates_because_no_rule_covers_it():
    assert request(order(status=OrderStatus.SHIPPED)).outcome == Outcome.ESCALATE


# ------------------------------------------------- return requests (R2, R3)


@pytest.mark.parametrize("days,expected", [(0, Outcome.RETURN_AUTHORIZED),
                                           (30, Outcome.RETURN_AUTHORIZED),
                                           (31, Outcome.DENY)])
def test_return_request_window_boundary(days, expected):
    d = request(order(days_since_delivery=days))
    assert d.outcome == expected
    assert d.amount_kobo == 0  # a return request never pays out


def test_return_authorized_lists_only_eligible_items():
    o = order(item(1), item(2, final_sale=True))
    d = request(o, ids=(1, 2))
    assert d.outcome == Outcome.RETURN_AUTHORIZED
    assert d.line_item_ids == (1,)


# ------------------------------------------------------------- R2 on receipt


def test_r2_unopened_within_30_days_full_refund():
    o = order(item(price=8_000))
    d = receive(o, received(o, days_after_delivery=30))
    assert d.outcome == Outcome.APPROVE
    assert d.amount_kobo == 8_000
    assert d.rule_ids == ("R2",)


def test_r2_unopened_day_31_denied():
    o = order(days_since_delivery=40)
    d = receive(o, received(o, days_after_delivery=31))
    assert d.outcome == Outcome.DENY


def test_r2_quantity_is_refunded_in_full():
    o = order(item(price=2_000, qty=3))
    assert receive(o, received(o)).amount_kobo == 6_000


# ------------------------------------------------------------- R3 on receipt


def test_r3_opened_within_15_days_charges_restocking_fee():
    o = order(item(price=10_000))
    d = receive(o, received(o, days_after_delivery=15, opened=True))
    assert d.outcome == Outcome.APPROVE
    assert d.amount_kobo == 8_500
    assert d.rule_ids == ("R3",)


def test_r3_opened_day_16_denied():
    o = order(days_since_delivery=20)
    d = receive(o, received(o, days_after_delivery=16, opened=True))
    assert d.outcome == Outcome.DENY
    assert d.rule_ids == ("R3",)


def test_r3_fashion_with_tags_has_no_fee():
    o = order(item(price=6_000, category="fashion"))
    d = receive(o, received(o, opened=True, tags=True))
    assert d.amount_kobo == 6_000


def test_r3_fashion_without_tags_pays_fee():
    o = order(item(price=6_000, category="fashion"))
    assert receive(o, received(o, opened=True, tags=False)).amount_kobo == 5_100


def test_r3_tags_do_not_waive_fee_outside_fashion():
    o = order(item(price=6_000, category="home"))
    assert receive(o, received(o, opened=True, tags=True)).amount_kobo == 5_100


def test_restocking_fee_rounds_half_up():
    assert restocking_fee_kobo(10) == 2  # 1.5 kobo rounds to 2
    assert restocking_fee_kobo(3_333) == 500  # 499.95 rounds to 500
    assert restocking_fee_kobo(0) == 0


def test_window_counts_from_request_not_arrival():
    """A return requested on day 14 that arrives on day 25 is still within R3."""
    o = order(days_since_delivery=25)
    d = receive(o, received(o, days_after_delivery=14, opened=True))
    assert d.outcome == Outcome.APPROVE


# ------------------------------------------------------------------- R4, R5


@pytest.mark.parametrize("days,expected", [(365, Outcome.ESCALATE), (366, Outcome.DENY)])
def test_r4_defective_always_escalates_within_one_year(days, expected):
    d = request(order(days_since_delivery=days), reason=ReasonCode.DEFECTIVE)
    assert d.outcome == expected
    assert d.rule_ids == ("R4",)
    assert d.amount_kobo == 0


@pytest.mark.parametrize("days,expected", [(7, Outcome.ESCALATE), (8, Outcome.DENY)])
def test_r5_damaged_always_escalates_within_7_days(days, expected):
    d = request(order(days_since_delivery=days), reason=ReasonCode.DAMAGED_IN_DELIVERY)
    assert d.outcome == expected
    assert d.rule_ids == ("R5",)
    assert d.amount_kobo == 0


def test_cheap_defective_item_still_escalates():
    d = request(order(item(price=100)), reason=ReasonCode.DEFECTIVE)
    assert d.outcome == Outcome.ESCALATE


# ----------------------------------------------------------------------- R6


@pytest.mark.parametrize("reason", [ReasonCode.RETURN, ReasonCode.DEFECTIVE,
                                    ReasonCode.DAMAGED_IN_DELIVERY])
def test_r6_final_sale_denied_for_every_reason(reason):
    d = request(order(item(final_sale=True)), reason=reason)
    assert d.outcome == Outcome.DENY
    assert d.rule_ids == ("R6",)


def test_r6_final_sale_denied_on_receipt():
    o = order(item(final_sale=True))
    assert receive(o, received(o)).outcome == Outcome.DENY


def test_mixed_request_escalates_whole_and_keeps_denial_reasons():
    o = order(item(1), item(2, final_sale=True))
    d = request(o, ids=(1, 2), reason=ReasonCode.DEFECTIVE)
    assert d.outcome == Outcome.ESCALATE
    assert {i.outcome for i in d.items} == {Outcome.ESCALATE, Outcome.DENY}


# ----------------------------------------------------------------------- R7


def test_r7_refund_is_capped_at_amount_paid():
    o = order(item(price=10_000), paid=7_000)  # e.g. a discount was applied
    d = receive(o, received(o))
    assert d.outcome == Outcome.APPROVE
    assert d.amount_kobo == 7_000
    assert "R7" in d.rule_ids


def test_r7_cap_counts_prior_refunds_on_the_order():
    o = order(item(1, price=6_000), item(2, price=6_000), paid=10_000)
    history = [refund(6_000, days_ago=1, order_id=100, line_item_ids=(1,))]
    d = receive(o, received(o, line_item_id=2), history=history)
    assert d.amount_kobo == 4_000


def test_r7_fully_refunded_order_is_denied():
    o = order(item(1), item(2), paid=5_000)
    history = [refund(5_000, days_ago=1, order_id=100, line_item_ids=(1,))]
    d = receive(o, received(o, line_item_id=2), history=history)
    assert d.outcome == Outcome.DENY
    assert "R7" in d.rule_ids


def test_r7_same_item_cannot_be_refunded_twice():
    o = order(item(1, price=5_000), item(2, price=5_000))
    history = [refund(5_000, days_ago=1, order_id=100, line_item_ids=(1,))]
    assert request(o, ids=(1,), history=history).outcome == Outcome.DENY
    assert receive(o, received(o, line_item_id=1), history=history).outcome == Outcome.DENY


# ----------------------------------------------------------------------- R8


@pytest.mark.parametrize("price,expected", [(LIMIT, Outcome.APPROVE),
                                            (LIMIT + 1, Outcome.ESCALATE)])
def test_r8_boundary_at_exactly_the_limit(price, expected):
    o = order(item(price=price))
    d = receive(o, received(o))
    assert d.outcome == expected


def test_r8_split_claims_on_one_order_still_escalate():
    """Twice the limit claimed as two refunds at the limit: the second one escalates."""
    o = order(item(1, price=LIMIT), item(2, price=LIMIT))
    first = receive(o, received(o, line_item_id=1))
    assert first.outcome == Outcome.APPROVE
    history = [refund(first.amount_kobo, days_ago=0, order_id=100, line_item_ids=(1,))]
    second = receive(o, received(o, line_item_id=2), history=history)
    assert second.outcome == Outcome.ESCALATE
    assert "R8" in second.rule_ids
    assert second.amount_kobo == 0


def test_r8_uses_amount_after_restocking_fee():
    """₦350,000 opened item: refund is ₦297,500 after the fee, under the ₦300,000 limit."""
    o = order(item(price=35_000_000))
    assert 35_000_000 > LIMIT
    d = receive(o, received(o, opened=True))
    assert d.outcome == Outcome.APPROVE
    assert d.amount_kobo == 29_750_000


# ----------------------------------------------------------------------- R9


def test_r9_third_refund_in_90_days_escalates():
    history = [refund(1_000, days_ago=10), refund(1_000, days_ago=20)]
    o = order()
    d = receive(o, received(o), history=history)
    assert d.outcome == Outcome.ESCALATE
    assert "R9" in d.rule_ids


def test_r9_second_refund_is_still_automatic():
    o = order()
    assert receive(o, received(o), history=[refund(1_000, days_ago=10)]).outcome == Outcome.APPROVE


@pytest.mark.parametrize("days_ago,expected", [(89, Outcome.ESCALATE), (90, Outcome.APPROVE)])
def test_r9_window_boundary(days_ago, expected):
    history = [refund(1_000, days_ago=5), refund(1_000, days_ago=days_ago)]
    o = order()
    assert receive(o, received(o), history=history).outcome == expected


def test_r9_counts_refunds_across_all_orders():
    history = [refund(1_000, days_ago=3, order_id=1), refund(1_000, days_ago=4, order_id=2)]
    d = evaluate_cancellation(order(status=OrderStatus.PLACED), tuple(history), NOW)
    assert d.outcome == Outcome.ESCALATE


# ---------------------------------------------------------- input validation


@pytest.mark.parametrize("ids", [(), (1, 1), (42,)])
def test_invalid_line_items_are_denied(ids):
    d = request(order(), ids=ids)
    assert d.outcome == Outcome.DENY
    assert d.amount_kobo == 0


def test_items_from_another_order_are_rejected_on_receipt():
    o = order()
    d = receive(o, ReceivedReturn(42, NOW, False, False))
    assert d.outcome == Outcome.DENY


# ---------------------------------------------------------------- R11, R12


def test_r11_identity_match_ignores_case_and_whitespace():
    assert identity_matches("Ada@Example.com", "  ada@example.com ")
    assert not identity_matches("ada@example.com", "ada@example.co")
    assert not identity_matches("ada@example.com", "")


def test_r12_address_change_only_before_shipping():
    assert evaluate_address_change(order(status=OrderStatus.PLACED)).outcome == Outcome.APPROVE
    for status in (OrderStatus.SHIPPED, OrderStatus.DELIVERED, OrderStatus.CANCELLED):
        assert evaluate_address_change(order(status=status)).outcome == Outcome.DENY


# --------------------------------------------------------------- invariants


def test_only_approve_decisions_carry_an_amount():
    """Across a sweep of inputs, a non-APPROVE decision never has a payable amount."""
    decisions: list[Decision] = []
    for status in OrderStatus:
        for days in (0, 7, 8, 15, 16, 30, 31, 365, 366):
            for reason in ReasonCode:
                o = order(item(price=30_000), status=status, days_since_delivery=days)
                decisions.append(request(o, reason=reason))
                if o.delivered_at:
                    for opened in (True, False):
                        decisions.append(receive(o, received(o, days_after_delivery=days, opened=opened)))
    for d in decisions:
        if d.outcome != Outcome.APPROVE:
            assert d.amount_kobo == 0, d
        assert d.amount_kobo <= 30_000
