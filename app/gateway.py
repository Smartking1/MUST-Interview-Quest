"""Payment gateways. Only app/executor.py (and the labelled-unsafe baseline) may hold one.

FakeGateway is the default (architecture invariant 9). Every call to any
gateway is written to the gateway_ledger table, which the eval scorers read.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clock import now
from app.models import GatewayLedger


class GatewayError(Exception):
    pass


@dataclass(frozen=True)
class GatewayResult:
    gateway_ref: str
    amount_cents: int


class PaymentGateway(Protocol):
    name: str

    def refund(
        self, session: Session, *, order_id: int, payment_ref: str | None,
        amount_cents: int, idempotency_key: str | None,
    ) -> GatewayResult: ...


class FakeGateway:
    """Records refunds without moving money. Idempotent on idempotency_key."""

    name = "fake"

    def __init__(self, agent: str = "trusted"):
        self.agent = agent

    def refund(
        self, session: Session, *, order_id: int, payment_ref: str | None,
        amount_cents: int, idempotency_key: str | None,
    ) -> GatewayResult:
        if amount_cents <= 0:
            raise GatewayError("Refund amount must be positive.")
        if idempotency_key:
            prior = session.scalar(
                select(GatewayLedger).where(GatewayLedger.idempotency_key == idempotency_key)
            )
            if prior:
                return GatewayResult(prior.gateway_ref, prior.amount_cents)
        ref = f"fake_re_{uuid.uuid4().hex[:16]}"
        session.add(GatewayLedger(
            agent=self.agent, order_id=order_id, amount_cents=amount_cents,
            idempotency_key=idempotency_key, gateway=self.name, gateway_ref=ref,
            created_at=now(),
        ))
        session.flush()
        return GatewayResult(ref, amount_cents)
