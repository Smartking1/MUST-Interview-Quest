"""Staff actions: approve or deny escalations, and receive returns at the warehouse.

A human approval produces a decision signed with issuer "human:<name>" and
goes through the same executor as policy decisions, so it gets the same
replay protection and the same live R7 cap. A human can override policy
limits like R8; nobody can pay more than the order's remaining balance.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.clock import now
from app.escalations import create_escalation, money
from app.executor import ExecutionRejected, Executor
from app.models import Escalation, Order, Return
from app.policy_engine import Decision, Outcome, evaluate_received_returns
from app.repository import order_snapshot, received_returns, refund_history
from app.signing import sign_decision


class AdminError(Exception):
    pass


@dataclass(frozen=True)
class AdminResult:
    message: str
    amount_kobo: int = 0


def open_escalations(s: Session) -> list[Escalation]:
    return list(s.scalars(select(Escalation).where(Escalation.status == "open").order_by(Escalation.id)))


def pending_returns(s: Session) -> list[Return]:
    return list(s.scalars(select(Return).where(Return.status == "authorized").order_by(Return.id)))


def _check_name(admin: str) -> str:
    admin = admin.strip()
    if not admin:
        raise AdminError("Enter your name so the decision is attributable.")
    return admin


def approve_escalation(
    sessions: sessionmaker[Session], executor: Executor, secret: bytes,
    escalation_id: int, admin: str, amount_kobo: int | None = None,
) -> AdminResult:
    admin = _check_name(admin)
    with sessions() as s:
        esc = s.get(Escalation, escalation_id)
        if esc is None or esc.status != "open":
            raise AdminError("Escalation not found or already resolved.")
        if esc.order_id is None:
            raise AdminError("No verified order on this escalation; reply to the customer by email instead.")
        amount = amount_kobo if amount_kobo is not None else esc.proposed_amount_kobo
        if not amount or amount <= 0:
            raise AdminError("Enter the refund amount for this case.")
        order = s.get(Order, esc.order_id)
        items = tuple(esc.line_item_ids) or tuple(i.id for i in order.items)
        decision = Decision(Outcome.APPROVE, order.id, items, tuple(esc.rule_ids) + ("HUMAN",),
                            f"Approved by {admin}", amount_kobo=amount)
    token = sign_decision(decision, secret, now(), issuer=f"human:{admin}")
    try:
        result = executor.execute(token)
    except ExecutionRejected as exc:
        raise AdminError(f"Executor rejected the approval: {exc}") from exc
    with sessions() as s:
        esc = s.get(Escalation, escalation_id)
        esc.status, esc.resolved_by = "approved", admin
        s.commit()
    return AdminResult(f"Refunded {money(result.amount_kobo)} ({result.gateway_ref}).", result.amount_kobo)


def deny_escalation(sessions: sessionmaker[Session], escalation_id: int, admin: str) -> AdminResult:
    admin = _check_name(admin)
    with sessions() as s:
        esc = s.get(Escalation, escalation_id)
        if esc is None or esc.status != "open":
            raise AdminError("Escalation not found or already resolved.")
        esc.status, esc.resolved_by = "denied", admin
        s.commit()
    return AdminResult("Denied. No money moved.")


def receive_return(
    sessions: sessionmaker[Session], executor: Executor, secret: bytes,
    return_id: int, opened: bool, tags_attached: bool,
) -> AdminResult:
    """Warehouse marks a return received and records its condition; policy decides the refund."""
    with sessions() as s:
        ret = s.get(Return, return_id)
        if ret is None or ret.status != "authorized":
            raise AdminError("Return not found or already received.")
        ret.status, ret.received_at, ret.opened, ret.tags_attached = "received", now(), opened, tags_attached
        order = s.scalar(select(Order).where(Order.items.any(id=ret.line_item_id)))
        d = evaluate_received_returns(order_snapshot(order), received_returns([ret]),
                                      refund_history(s, order.customer_id), now())
        if d.outcome == Outcome.ESCALATE:
            esc = create_escalation(s, order, f"Refund for received return {ret.id}", d.rule_ids, d.reason,
                                    d.proposed_amount_kobo, d.line_item_ids)
            s.commit()
            return AdminResult(f"Return received. Refund needs approval (escalation {esc.id}): {d.reason}")
        s.commit()
        if d.outcome == Outcome.DENY:
            return AdminResult(f"Return received. No refund: {d.reason} Rules: {', '.join(d.rule_ids)}.")
    try:
        result = executor.execute(sign_decision(d, secret, now()))
    except ExecutionRejected as exc:
        raise AdminError(f"Executor rejected the refund: {exc}") from exc
    return AdminResult(f"Return received. Refunded {money(result.amount_kobo)} under {', '.join(d.rule_ids)}.",
                       result.amount_kobo)
