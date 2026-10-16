"""Create a Stripe TEST-MODE payment for every seeded order that has been paid.

Each order gets a confirmed PaymentIntent using Stripe's test card
(pm_card_visa), stored in orders.gateway_payment_ref, so the executor has a
real test payment to refund. Orders whose seeded refunds already exist get
those refunds mirrored in Stripe, so Stripe's balance matches the database.

Run after seeding: uv run python -m app.stripe_setup
"""

from __future__ import annotations

import os

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import make_engine
from app.gateway import StripeGateway
from app.models import Order, Refund


def main() -> None:
    gw = StripeGateway(os.environ.get("STRIPE_SECRET_KEY", ""), os.environ.get("STRIPE_API_BASE"))
    client = gw._client
    with Session(make_engine()) as s:
        for order in s.scalars(select(Order).order_by(Order.id)):
            if order.gateway_payment_ref:
                continue
            pi = client.v1.payment_intents.create(
                params={"amount": order.paid_cents, "currency": "usd", "payment_method": "pm_card_visa",
                        "confirm": True, "automatic_payment_methods": {"enabled": True, "allow_redirects": "never"},
                        "description": f"Harbor Market {order.order_number} (test mode)",
                        "metadata": {"order_number": order.order_number}},
                options={"idempotency_key": f"harbor-pi-{order.order_number}-{order.created_at.date()}"},
            )
            order.gateway_payment_ref = pi.id
            for r in s.scalars(select(Refund).where(Refund.order_id == order.id, Refund.issuer == "seed")):
                client.v1.refunds.create(params={"payment_intent": pi.id, "amount": r.amount_cents},
                                         options={"idempotency_key": r.decision_id})
            print(f"{order.order_number}: {pi.id} ({pi.status})")
        s.commit()


if __name__ == "__main__":
    main()
