"""Builds policy engine snapshots from the database."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clock import as_utc
from app.models import Order, Refund, Return
from app.policy_engine import (
    ItemSnapshot,
    OrderSnapshot,
    OrderStatus,
    ReceivedReturn,
    RefundRecord,
)


def order_snapshot(order: Order) -> OrderSnapshot:
    return OrderSnapshot(
        order_id=order.id,
        customer_id=order.customer_id,
        status=OrderStatus(order.status),
        paid_cents=order.paid_cents,
        items=tuple(
            ItemSnapshot(i.id, i.category, i.price_cents, i.qty, i.final_sale)
            for i in sorted(order.items, key=lambda i: i.id)
        ),
        delivered_at=as_utc(order.delivered_at) if order.delivered_at else None,
    )


def refund_history(session: Session, customer_id: int) -> tuple[RefundRecord, ...]:
    rows = session.scalars(select(Refund).where(Refund.customer_id == customer_id))
    return tuple(
        RefundRecord(r.order_id, r.amount_cents, as_utc(r.created_at), tuple(r.line_item_ids))
        for r in rows
    )


def received_returns(returns: list[Return]) -> tuple[ReceivedReturn, ...]:
    return tuple(
        ReceivedReturn(r.line_item_id, as_utc(r.requested_at), bool(r.opened), bool(r.tags_attached))
        for r in returns
    )


def find_order(session: Session, order_number: str) -> Order | None:
    return session.scalar(select(Order).where(Order.order_number == order_number.strip().upper()))
