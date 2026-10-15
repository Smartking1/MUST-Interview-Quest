"""Deterministic policy engine for Harbor Market (policy/policy.md).

Pure functions only: no LLM, no database, no clock. Callers pass in snapshots
of the order, the customer's refund history and the current time. The model
never supplies an amount; every amount here is computed from snapshot data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

AUTO_APPROVAL_LIMIT_CENTS = 20_000  # R8: over $200 needs a human
FREQUENCY_WINDOW_DAYS = 90  # R9
FREQUENCY_MAX_AUTO = 2  # R9: more than 2 refunds in the window needs a human
RESTOCKING_FEE_PERCENT = 15  # R3
UNOPENED_WINDOW_DAYS = 30  # R2
OPENED_WINDOW_DAYS = 15  # R3
DEFECTIVE_WINDOW_DAYS = 365  # R4
DAMAGED_WINDOW_DAYS = 7  # R5


class Outcome(StrEnum):
    APPROVE = "approve"
    DENY = "deny"
    ESCALATE = "escalate"
    RETURN_AUTHORIZED = "return_authorized"


class ReasonCode(StrEnum):
    CANCEL_UNSHIPPED = "cancel_unshipped"
    RETURN = "return"
    DEFECTIVE = "defective"
    DAMAGED_IN_DELIVERY = "damaged_in_delivery"


class OrderStatus(StrEnum):
    PLACED = "placed"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class ItemSnapshot:
    line_item_id: int
    category: str  # electronics, fashion, home
    price_cents: int  # per unit
    qty: int
    final_sale: bool

    @property
    def total_cents(self) -> int:
        return self.price_cents * self.qty


@dataclass(frozen=True)
class OrderSnapshot:
    order_id: int
    customer_id: int
    status: OrderStatus
    paid_cents: int
    items: tuple[ItemSnapshot, ...]
    delivered_at: datetime | None = None


@dataclass(frozen=True)
class RefundRecord:
    """A refund already executed for this customer, on any order."""

    order_id: int
    amount_cents: int
    created_at: datetime
    line_item_ids: tuple[int, ...] = ()


@dataclass(frozen=True)
class ReceivedReturn:
    """Recorded by the warehouse when the item arrives, never by the customer."""

    line_item_id: int
    requested_at: datetime
    opened: bool
    tags_attached: bool


@dataclass(frozen=True)
class ItemOutcome:
    line_item_id: int
    outcome: Outcome
    rule_ids: tuple[str, ...]
    amount_cents: int = 0
    reason: str = ""


@dataclass(frozen=True)
class Decision:
    outcome: Outcome
    order_id: int
    line_item_ids: tuple[int, ...]
    rule_ids: tuple[str, ...]
    reason: str
    amount_cents: int = 0  # non-zero only for APPROVE
    proposed_amount_cents: int | None = None  # for a human reviewing an ESCALATE
    items: tuple[ItemOutcome, ...] = field(default_factory=tuple)


# ---------------------------------------------------------------- helpers


def days_between(start: datetime, end: datetime) -> int:
    """Whole calendar days from start to end, by date. Same day is 0."""
    return (end.date() - start.date()).days


def _unique(ids: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(ids))


def restocking_fee_cents(amount_cents: int) -> int:
    """15% of the amount, rounded half up to the nearest cent."""
    return (amount_cents * RESTOCKING_FEE_PERCENT + 50) // 100


def identity_matches(order_email: str, given_email: str) -> bool:
    """R11: the email given must match the email on the order."""
    return order_email.strip().casefold() == given_email.strip().casefold()


def _refunded_on_order(order_id: int, history: tuple[RefundRecord, ...]) -> int:
    return sum(r.amount_cents for r in history if r.order_id == order_id)


def _refunded_item_ids(order_id: int, history: tuple[RefundRecord, ...]) -> set[int]:
    return {i for r in history if r.order_id == order_id for i in r.line_item_ids}


def _recent_refund_count(history: tuple[RefundRecord, ...], now: datetime) -> int:
    """R9: refunds in the last 90 days, counting a refund made 89 days ago but not 90."""
    return sum(1 for r in history if days_between(r.created_at, now) < FREQUENCY_WINDOW_DAYS)


def _validate_items(
    order: OrderSnapshot, line_item_ids: tuple[int, ...]
) -> tuple[dict[int, ItemSnapshot], str | None]:
    by_id = {i.line_item_id: i for i in order.items}
    if not line_item_ids:
        return by_id, "No items were specified."
    if len(set(line_item_ids)) != len(line_item_ids):
        return by_id, "The same item was listed more than once."
    unknown = [i for i in line_item_ids if i not in by_id]
    if unknown:
        return by_id, f"Items {unknown} are not on this order."
    return by_id, None


def _apply_money_limits(
    order: OrderSnapshot,
    amount_cents: int,
    rule_ids: tuple[str, ...],
    line_item_ids: tuple[int, ...],
    items: tuple[ItemOutcome, ...],
    history: tuple[RefundRecord, ...],
    now: datetime,
) -> Decision:
    """R7, R8, R9 applied to any refund about to be approved. All are cumulative."""
    already = _refunded_on_order(order.order_id, history)
    remaining = order.paid_cents - already
    if remaining <= 0:
        return Decision(
            Outcome.DENY, order.order_id, line_item_ids, _unique(rule_ids + ("R7",)),
            "This order has already been refunded in full.", items=items,
        )
    if amount_cents > remaining:
        amount_cents = remaining
        rule_ids = rule_ids + ("R7",)

    if already + amount_cents > AUTO_APPROVAL_LIMIT_CENTS:
        return Decision(
            Outcome.ESCALATE, order.order_id, line_item_ids, _unique(rule_ids + ("R8",)),
            "Refunds on this order would total more than $200, which needs human approval.",
            proposed_amount_cents=amount_cents, items=items,
        )
    if _recent_refund_count(history, now) >= FREQUENCY_MAX_AUTO:
        return Decision(
            Outcome.ESCALATE, order.order_id, line_item_ids, _unique(rule_ids + ("R9",)),
            "This would be more than 2 refunds in 90 days, which needs human approval.",
            proposed_amount_cents=amount_cents, items=items,
        )
    return Decision(
        Outcome.APPROVE, order.order_id, line_item_ids, _unique(rule_ids),
        "Refund approved under policy.", amount_cents=amount_cents, items=items,
    )


def _aggregate(
    order: OrderSnapshot,
    line_item_ids: tuple[int, ...],
    items: tuple[ItemOutcome, ...],
    history: tuple[RefundRecord, ...],
    now: datetime,
    approve_outcome: Outcome,
) -> Decision:
    """Combine per-item outcomes. Any escalation escalates the whole request."""
    rule_ids = _unique([r for i in items for r in i.rule_ids])
    escalated = [i for i in items if i.outcome == Outcome.ESCALATE]
    approved = [i for i in items if i.outcome == approve_outcome]

    if escalated:
        return Decision(
            Outcome.ESCALATE, order.order_id, line_item_ids, rule_ids,
            "; ".join(i.reason for i in escalated), items=items,
        )
    if not approved:
        return Decision(
            Outcome.DENY, order.order_id, line_item_ids, rule_ids,
            "; ".join(i.reason for i in items), items=items,
        )
    if approve_outcome == Outcome.RETURN_AUTHORIZED:
        return Decision(
            Outcome.RETURN_AUTHORIZED, order.order_id,
            tuple(i.line_item_id for i in approved), rule_ids,
            "Return authorized. The refund is decided when the return is received.",
            items=items,
        )
    return _apply_money_limits(
        order, sum(i.amount_cents for i in approved), rule_ids,
        tuple(i.line_item_id for i in approved), items, history, now,
    )


# --------------------------------------------------------------- decisions


def evaluate_cancellation(
    order: OrderSnapshot, history: tuple[RefundRecord, ...], now: datetime
) -> Decision:
    """R1: an unshipped order can be cancelled for a full refund."""
    all_items = tuple(i.line_item_id for i in order.items)
    if order.status == OrderStatus.CANCELLED:
        return Decision(Outcome.DENY, order.order_id, all_items, ("R1",),
                        "This order is already cancelled.")
    if order.status != OrderStatus.PLACED:
        return Decision(Outcome.DENY, order.order_id, all_items, ("R1",),
                        "This order has already shipped, so it cannot be cancelled.")
    return _apply_money_limits(order, order.paid_cents, ("R1",), all_items, (), history, now)


def evaluate_request(
    order: OrderSnapshot,
    line_item_ids: tuple[int, ...],
    reason: ReasonCode,
    history: tuple[RefundRecord, ...],
    now: datetime,
) -> Decision:
    """Evaluate a customer's refund or return request on delivered items.

    RETURN never pays out here: it authorizes the return, and the refund is
    decided by evaluate_received_returns using the condition the warehouse
    records. DEFECTIVE and DAMAGED_IN_DELIVERY always escalate when in window.
    """
    if reason == ReasonCode.CANCEL_UNSHIPPED:
        return evaluate_cancellation(order, history, now)

    by_id, error = _validate_items(order, line_item_ids)
    if error:
        return Decision(Outcome.DENY, order.order_id, line_item_ids, (), error)

    if order.status == OrderStatus.PLACED:
        return Decision(Outcome.DENY, order.order_id, line_item_ids, ("R1",),
                        "This order has not shipped yet. It can be cancelled instead.")
    if order.status == OrderStatus.CANCELLED:
        return Decision(Outcome.DENY, order.order_id, line_item_ids, ("R1",),
                        "This order is cancelled.")
    if order.status != OrderStatus.DELIVERED or order.delivered_at is None:
        return Decision(Outcome.ESCALATE, order.order_id, line_item_ids, (),
                        "The order has shipped but is not marked delivered; no rule covers this case.")

    days = days_between(order.delivered_at, now)
    refunded = _refunded_item_ids(order.order_id, history)
    outcomes: list[ItemOutcome] = []
    for item_id in line_item_ids:
        item = by_id[item_id]
        if item_id in refunded:
            outcomes.append(ItemOutcome(item_id, Outcome.DENY, ("R7",),
                                        reason="This item has already been refunded."))
        elif item.final_sale:
            outcomes.append(ItemOutcome(item_id, Outcome.DENY, ("R6",),
                                        reason="Final sale items are not refundable."))
        elif reason == ReasonCode.RETURN:
            if days <= UNOPENED_WINDOW_DAYS:
                outcomes.append(ItemOutcome(item_id, Outcome.RETURN_AUTHORIZED, ("R2", "R3")))
            else:
                outcomes.append(ItemOutcome(item_id, Outcome.DENY, ("R2", "R3"),
                                            reason="The 30 day return window has passed."))
        elif reason == ReasonCode.DEFECTIVE:
            if days <= DEFECTIVE_WINDOW_DAYS:
                outcomes.append(ItemOutcome(item_id, Outcome.ESCALATE, ("R4",),
                                            reason="Defective item claims are reviewed by staff."))
            else:
                outcomes.append(ItemOutcome(item_id, Outcome.DENY, ("R4",),
                                            reason="The 1 year defect window has passed."))
        elif reason == ReasonCode.DAMAGED_IN_DELIVERY:
            if days <= DAMAGED_WINDOW_DAYS:
                outcomes.append(ItemOutcome(item_id, Outcome.ESCALATE, ("R5",),
                                            reason="Delivery damage claims are reviewed by staff."))
            else:
                outcomes.append(ItemOutcome(item_id, Outcome.DENY, ("R5",),
                                            reason="Delivery damage must be reported within 7 days."))

    return _aggregate(order, line_item_ids, tuple(outcomes), history, now,
                      approve_outcome=Outcome.RETURN_AUTHORIZED)


def evaluate_received_returns(
    order: OrderSnapshot,
    received: tuple[ReceivedReturn, ...],
    history: tuple[RefundRecord, ...],
    now: datetime,
) -> Decision:
    """R2, R3: decide the refund once returns are received, from warehouse data.

    The return date that counts against the window is when the return was
    requested (authorized), not when it arrived.
    """
    line_item_ids = tuple(r.line_item_id for r in received)
    by_id, error = _validate_items(order, line_item_ids)
    if error:
        return Decision(Outcome.DENY, order.order_id, line_item_ids, (), error)
    if order.delivered_at is None:
        return Decision(Outcome.ESCALATE, order.order_id, line_item_ids, (),
                        "Return received for an order not marked delivered.")

    refunded = _refunded_item_ids(order.order_id, history)
    outcomes: list[ItemOutcome] = []
    for ret in received:
        item = by_id[ret.line_item_id]
        days = days_between(order.delivered_at, ret.requested_at)
        if ret.line_item_id in refunded:
            outcomes.append(ItemOutcome(item.line_item_id, Outcome.DENY, ("R7",),
                                        reason="This item has already been refunded."))
        elif item.final_sale:
            outcomes.append(ItemOutcome(item.line_item_id, Outcome.DENY, ("R6",),
                                        reason="Final sale items are not refundable."))
        elif not ret.opened:
            if days <= UNOPENED_WINDOW_DAYS:
                outcomes.append(ItemOutcome(item.line_item_id, Outcome.APPROVE, ("R2",),
                                            amount_cents=item.total_cents))
            else:
                outcomes.append(ItemOutcome(item.line_item_id, Outcome.DENY, ("R2",),
                                            reason="Returned after the 30 day window."))
        elif days > OPENED_WINDOW_DAYS:
            outcomes.append(ItemOutcome(item.line_item_id, Outcome.DENY, ("R3",),
                                        reason="Opened items must be returned within 15 days."))
        elif item.category == "fashion" and ret.tags_attached:
            outcomes.append(ItemOutcome(item.line_item_id, Outcome.APPROVE, ("R3",),
                                        amount_cents=item.total_cents))
        else:
            fee = restocking_fee_cents(item.total_cents)
            outcomes.append(ItemOutcome(item.line_item_id, Outcome.APPROVE, ("R3",),
                                        amount_cents=item.total_cents - fee,
                                        reason="15% restocking fee applied."))

    return _aggregate(order, line_item_ids, tuple(outcomes), history, now,
                      approve_outcome=Outcome.APPROVE)


def evaluate_address_change(order: OrderSnapshot) -> Decision:
    """R12: address changes only before shipping."""
    all_items = tuple(i.line_item_id for i in order.items)
    if order.status == OrderStatus.PLACED:
        return Decision(Outcome.APPROVE, order.order_id, all_items, ("R12",),
                        "Address can be changed.")
    return Decision(Outcome.DENY, order.order_id, all_items, ("R12",),
                    "The address can only be changed before the order ships.")

