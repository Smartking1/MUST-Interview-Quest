"""Escalations to staff (architecture invariant 10).

The summary is built from database records, not from the model's words, so
a human can act on it in under 30 seconds and the model cannot misdescribe
the case.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.clock import now
from app.models import Customer, Escalation, Order


def money(kobo: int) -> str:
    return f"₦{kobo / 100:,.2f}"


def describe_order(order: Order) -> str:
    lines = [
        f"Order {order.order_number}: status {order.status}, paid {money(order.paid_kobo)}.",
        f"Shipping address: {order.shipping_address}.",
    ]
    if order.delivered_at:
        lines.append(f"Delivered on {order.delivered_at.date().isoformat()}.")
    elif order.shipped_at:
        lines.append(f"Shipped on {order.shipped_at.date().isoformat()}.")
    for i in sorted(order.items, key=lambda i: i.id):
        flag = ", final sale" if i.final_sale else ""
        lines.append(f"- line_item_id {i.id}: {i.name} ({i.category}), {i.qty} x {money(i.price_kobo)}{flag}")
    return "\n".join(lines)


def create_escalation(
    s: Session, order: Order | None, request: str, rule_ids: tuple[str, ...], reason: str,
    proposed: int | None = None, line_item_ids: tuple[int, ...] = (),
    customer_id: int | None = None, last_message: str = "",
) -> Escalation:
    cid = order.customer_id if order else customer_id
    customer = s.get(Customer, cid) if cid else None
    who = f"{customer.name} <{customer.email}>" if customer else "unverified customer"
    parts = [
        f"Customer: {who}",
        f"Order: {describe_order(order)}" if order else "Order: none verified",
        f"Request: {request}",
        f"Customer's last message: {last_message!r}" if last_message else "Source: staff action",
        f"Rules: {', '.join(rule_ids) or 'none'}",
        f"Why escalated: {reason}",
    ]
    if proposed is not None:
        parts.append(f"Amount policy would pay if approved: {money(proposed)}")
    esc = Escalation(
        customer_id=customer.id if customer else None, order_id=order.id if order else None,
        line_item_ids=list(line_item_ids), request=request, rule_ids=list(rule_ids), reason=reason,
        summary="\n".join(parts), proposed_amount_kobo=proposed, status="open", created_at=now(),
    )
    s.add(esc)
    s.flush()
    return esc
