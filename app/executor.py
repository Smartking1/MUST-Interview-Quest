"""The only component that can move money (architecture invariants 2 and 3).

It accepts nothing but a signed decision. It rejects unsigned, altered,
expired and reused decisions, re-checks the R7 cap against the live database,
and calls the gateway with decision_id as the idempotency key. No language
model can reach this module: tools pass it tokens they never show the model.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.clock import now
from app.gateway import PaymentGateway
from app.models import Order, Refund
from app.signing import InvalidDecision, SignedPayload, verify


class ExecutionRejected(Exception):
    pass


@dataclass(frozen=True)
class ExecutionResult:
    decision_id: str
    order_id: int
    amount_cents: int
    gateway_ref: str


class Executor:
    def __init__(self, session_factory: sessionmaker[Session], gateway: PaymentGateway, secret: bytes):
        self._sessions = session_factory
        self._gateway = gateway
        self._secret = secret

    def execute(self, token: str) -> ExecutionResult:
        try:
            payload = verify(token, self._secret, now())
        except InvalidDecision as exc:
            raise ExecutionRejected(str(exc)) from exc

        with self._sessions() as session:
            try:
                result = self._execute(session, payload)
                session.commit()
            except IntegrityError as exc:
                session.rollback()
                raise ExecutionRejected("Decision has already been used.") from exc
            except Exception:
                session.rollback()
                raise
        return result

    def _execute(self, session: Session, p: SignedPayload) -> ExecutionResult:
        if session.scalar(select(Refund.id).where(Refund.decision_id == p.decision_id)):
            raise ExecutionRejected("Decision has already been used.")
        order = session.get(Order, p.order_id)
        if order is None:
            raise ExecutionRejected("Order does not exist.")
        if not set(p.line_item_ids) <= {i.id for i in order.items}:
            raise ExecutionRejected("Decision names items that are not on this order.")

        prior = list(session.scalars(select(Refund).where(Refund.order_id == order.id)))
        if sum(r.amount_cents for r in prior) + p.amount_cents > order.paid_cents:
            raise ExecutionRejected("Refund would exceed the amount paid (R7).")
        already = {i for r in prior for i in r.line_item_ids}
        if "R1" not in p.rule_ids and already & set(p.line_item_ids):
            raise ExecutionRejected("An item in this decision has already been refunded (R7).")

        refund = Refund(
            decision_id=p.decision_id, order_id=order.id, customer_id=order.customer_id,
            line_item_ids=list(p.line_item_ids), amount_cents=p.amount_cents,
            rule_ids=list(p.rule_ids), issuer=p.issuer, created_at=now(),
        )
        session.add(refund)
        session.flush()  # unique decision_id: a replayed decision fails here, before any money moves

        result = self._gateway.refund(
            session, order_id=order.id, payment_ref=order.gateway_payment_ref,
            amount_cents=p.amount_cents, idempotency_key=p.decision_id,
        )
        refund.gateway_ref = result.gateway_ref
        if "R1" in p.rule_ids:
            order.status = "cancelled"
        return ExecutionResult(p.decision_id, order.id, p.amount_cents, result.gateway_ref)
