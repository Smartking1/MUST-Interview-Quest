"""Payment gateways. Only app/executor.py (and the labelled-unsafe baseline) may hold one.

FakeGateway is the default (architecture invariant 9). Every call to any
gateway is written to the gateway_ledger table, which the eval scorers read.
"""

from __future__ import annotations

import os
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


class StripeGateway:
    """Stripe refunds in TEST MODE only (architecture invariant 9).

    Refuses live keys at construction, so the app refuses to start on one.
    Refunds the order's PaymentIntent with decision_id as Stripe's
    idempotency key, so a retried decision can never refund twice.
    """

    name = "stripe"

    def __init__(self, api_key: str, api_base: str | None = None, client=None, agent: str = "trusted"):
        check_test_key(api_key, prefix="sk_test_", allow_any=api_base is not None)
        self.agent = agent
        if client is None:
            import stripe

            kwargs = {"base_addresses": {"api": api_base}} if api_base else {}
            client = stripe.StripeClient(api_key, max_network_retries=2, **kwargs)
        self._client = client

    def refund(
        self, session: Session, *, order_id: int, payment_ref: str | None,
        amount_cents: int, idempotency_key: str | None,
    ) -> GatewayResult:
        if amount_cents <= 0:
            raise GatewayError("Refund amount must be positive.")
        if not payment_ref:
            raise GatewayError("Order has no Stripe payment to refund. Run app.stripe_setup first.")
        options = {"idempotency_key": idempotency_key} if idempotency_key else None
        refund = self._client.v1.refunds.create(
            params={"payment_intent": payment_ref, "amount": amount_cents,
                    "metadata": {"order_id": str(order_id), "decision_id": idempotency_key or ""}},
            options=options,
        )
        session.add(GatewayLedger(
            agent=self.agent, order_id=order_id, amount_cents=refund.amount,
            idempotency_key=idempotency_key, gateway=self.name, gateway_ref=refund.id,
            created_at=now(),
        ))
        session.flush()
        return GatewayResult(refund.id, refund.amount)


def check_test_key(key: str, prefix: str, allow_any: bool = False) -> None:
    if not key:
        raise GatewayError("No payment API key set.")
    if "_live_" in key:
        raise GatewayError("Refusing to start: a LIVE payment key was supplied. Use a test-mode key.")
    if not allow_any and not key.startswith(prefix):
        raise GatewayError(f"Payment key must be a test key starting with {prefix!r}.")


def gateway_from_env() -> PaymentGateway:
    """PAYMENT_GATEWAY=fake (default) or stripe (needs STRIPE_SECRET_KEY, test mode only).

    STRIPE_API_BASE points at a local stripe-mock (for example http://localhost:12111).
    """
    kind = os.environ.get("PAYMENT_GATEWAY", "fake")
    if kind == "fake":
        return FakeGateway("trusted")
    if kind == "stripe":
        return StripeGateway(os.environ.get("STRIPE_SECRET_KEY", ""), os.environ.get("STRIPE_API_BASE"))
    raise GatewayError(f"Unknown PAYMENT_GATEWAY {kind!r}")
