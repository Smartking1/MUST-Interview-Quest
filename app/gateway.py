"""Payment gateways. Only app/executor.py (and the labelled-unsafe baseline) may hold one.

FakeGateway is the default (architecture invariant 9). Every call to any
gateway is written to the gateway_ledger table, which the eval scorers read.
"""

from __future__ import annotations

import os
import uuid

import httpx
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clock import now
from app.models import GatewayLedger


class GatewayError(Exception):
    pass


class GatewayRejected(GatewayError):
    """The gateway definitely did not move money. Anything else is an unknown outcome."""


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
            raise GatewayRejected("Refund amount must be positive.")
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


class PaystackGateway:
    """Paystack refunds in TEST MODE only (architecture invariant 9).

    Refuses anything but an sk_test_ key, so the app refuses to start on a
    live key. Paystack refunds take no idempotency key; the executor's
    two-phase claim provides that guarantee, and the decision_id is sent as
    the merchant note so any refund can be traced in the Paystack dashboard.

    Amounts: the store prices in USD cents. A Nigerian Paystack test account
    settles in NGN, so test refunds are sent in PAYSTACK_CURRENCY subunits
    one to one (1 US cent = 1 kobo by default). This is a test-mode
    convenience, stated in the README, not a conversion.
    """

    name = "paystack"

    def __init__(self, secret_key: str, currency: str = "NGN", client: httpx.Client | None = None,
                 agent: str = "trusted", base_url: str = "https://api.paystack.co"):
        check_test_key(secret_key, prefix="sk_test_")
        self.agent = agent
        self.currency = currency
        self._http = client or httpx.Client(
            base_url=base_url, timeout=30, headers={"Authorization": f"Bearer {secret_key}"})

    def refund(
        self, session: Session, *, order_id: int, payment_ref: str | None,
        amount_cents: int, idempotency_key: str | None,
    ) -> GatewayResult:
        if amount_cents <= 0:
            raise GatewayRejected("Refund amount must be positive.")
        if not payment_ref:
            raise GatewayRejected("Order has no Paystack payment to refund. Run app.paystack_setup first.")
        response = self._http.post("/refund", json={
            "transaction": payment_ref, "amount": amount_cents, "currency": self.currency,
            "merchant_note": f"Trusted Support decision {idempotency_key}",
        })
        if 400 <= response.status_code < 500:
            raise GatewayRejected(f"Paystack rejected the refund: {_message(response)}")
        response.raise_for_status()  # 5xx: outcome unknown, the executor leaves the refund pending
        data = response.json()["data"]
        ref = f"paystack_refund_{data['id']}"
        session.add(GatewayLedger(
            agent=self.agent, order_id=order_id, amount_cents=amount_cents,
            idempotency_key=idempotency_key, gateway=self.name, gateway_ref=ref, created_at=now(),
        ))
        session.flush()
        return GatewayResult(ref, amount_cents)


def _message(response: httpx.Response) -> str:
    try:
        return response.json().get("message", response.text)
    except ValueError:
        return response.text


def check_test_key(key: str, prefix: str) -> None:
    if not key:
        raise GatewayError("No payment API key set.")
    if "_live_" in key:
        raise GatewayError("Refusing to start: a LIVE payment key was supplied. Use a test-mode key.")
    if not key.startswith(prefix):
        raise GatewayError(f"Payment key must be a test key starting with {prefix!r}.")


def gateway_from_env() -> PaymentGateway:
    """PAYMENT_GATEWAY=fake (default) or paystack (needs PAYSTACK_SECRET_KEY, test mode only)."""
    kind = os.environ.get("PAYMENT_GATEWAY", "fake")
    if kind == "fake":
        return FakeGateway("trusted")
    if kind == "paystack":
        return PaystackGateway(os.environ.get("PAYSTACK_SECRET_KEY", ""),
                               os.environ.get("PAYSTACK_CURRENCY", "NGN"))
    raise GatewayError(f"Unknown PAYMENT_GATEWAY {kind!r}")
