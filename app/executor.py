"""The only component that can move money (architecture invariants 2 and 3).

It accepts nothing but a signed decision. It rejects unsigned, altered,
expired and reused decisions, re-checks the R7 cap against the live database,
and calls the gateway. No language model can reach this module: tools pass it
tokens they never show the model.

Two-phase, because not every gateway is idempotent (Paystack refunds take no
idempotency key):
1. Claim the decision: commit a `pending` refund row. The unique decision_id
   makes a second claim fail before any money can move.
2. Call the gateway, then mark the row `succeeded`, or `failed` only when the
   gateway definitely rejected it. A timeout or server error leaves it `pending`.
If the process dies between the gateway call and step 2, the row stays
`pending` and counts against R7. It is never retried automatically: a human
reconciles it using the decision_id, which is sent to the gateway as a note.
Pending and succeeded refunds both count toward every limit; failed ones do not.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.clock import now
from app.gateway import GatewayRejected, PaymentGateway
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


def counted_refunds(session: Session, order_id: int) -> list[Refund]:
    """Refunds that count toward limits: everything except definite failures."""
    return list(session.scalars(select(Refund).where(Refund.order_id == order_id, Refund.status != "failed")))


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

        refund_id, payment_ref = self._claim(payload)

        with self._sessions() as session:
            try:
                result = self._gateway.refund(
                    session, order_id=payload.order_id, payment_ref=payment_ref,
                    amount_cents=payload.amount_cents, idempotency_key=payload.decision_id,
                )
            except GatewayRejected:
                session.rollback()
                self._finish(refund_id, "failed", None)
                raise
            except Exception:
                session.rollback()
                raise  # outcome unknown: the refund stays pending for a human to reconcile
            session.commit()  # the gateway's ledger entry
        self._finish(refund_id, "succeeded", result.gateway_ref, cancel="R1" in payload.rule_ids)
        return ExecutionResult(payload.decision_id, payload.order_id, payload.amount_cents, result.gateway_ref)

    def _claim(self, p: SignedPayload) -> tuple[int, str | None]:
        with self._sessions() as session:
            if session.scalar(select(Refund.id).where(Refund.decision_id == p.decision_id)):
                raise ExecutionRejected("Decision has already been used.")
            order = session.get(Order, p.order_id)
            if order is None:
                raise ExecutionRejected("Order does not exist.")
            if not set(p.line_item_ids) <= {i.id for i in order.items}:
                raise ExecutionRejected("Decision names items that are not on this order.")

            prior = counted_refunds(session, order.id)
            if sum(r.amount_cents for r in prior) + p.amount_cents > order.paid_cents:
                raise ExecutionRejected("Refund would exceed the amount paid (R7).")
            already = {i for r in prior for i in r.line_item_ids}
            if "R1" not in p.rule_ids and already & set(p.line_item_ids):
                raise ExecutionRejected("An item in this decision has already been refunded (R7).")

            refund = Refund(
                decision_id=p.decision_id, order_id=order.id, customer_id=order.customer_id,
                line_item_ids=list(p.line_item_ids), amount_cents=p.amount_cents,
                rule_ids=list(p.rule_ids), issuer=p.issuer, status="pending", created_at=now(),
            )
            session.add(refund)
            try:
                session.commit()  # the claim: a replay fails here, before any money moves
            except IntegrityError as exc:
                session.rollback()
                raise ExecutionRejected("Decision has already been used.") from exc
            return refund.id, order.gateway_payment_ref

    def _finish(self, refund_id: int, status: str, gateway_ref: str | None, cancel: bool = False) -> None:
        with self._sessions() as session:
            refund = session.get(Refund, refund_id)
            refund.status, refund.gateway_ref = status, gateway_ref
            if cancel:
                session.get(Order, refund.order_id).status = "cancelled"
            session.commit()
