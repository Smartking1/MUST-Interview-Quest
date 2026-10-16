"""Create real Paystack TEST-MODE payments for the seeded orders.

Paystack's API takes no raw card details, so the first payment goes through
hosted checkout with a Paystack test card. Its reusable authorization then
pays for every other order by API.

  1. uv run python -m app.paystack_setup checkout
     Opens a checkout for HM-1001. Pay with a test card from
     https://paystack.com/docs/payments/test-payments/
  2. uv run python -m app.paystack_setup finish <reference printed in step 1>
     Verifies that payment, charges the other orders with the same
     authorization, mirrors the seeded refunds, and saves all references.

Amounts are the store's cents sent one to one as PAYSTACK_CURRENCY subunits.
"""

from __future__ import annotations

import os
import sys
import uuid

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import payment_refs
from app.db import make_engine
from app.gateway import check_test_key
from app.models import Order, Refund
from app.seed import ORDERS

FIRST_ORDER = "HM-1001"


def client() -> httpx.Client:
    key = os.environ.get("PAYSTACK_SECRET_KEY", "")
    check_test_key(key, "sk_test_")
    return httpx.Client(base_url="https://api.paystack.co", timeout=30,
                        headers={"Authorization": f"Bearer {key}"})


def payer_email() -> str:
    return os.environ.get("PAYSTACK_PAYER_EMAIL", "harbor.demo@example.com")


def currency() -> str:
    return os.environ.get("PAYSTACK_CURRENCY", "NGN")


def paid_cents(number: str) -> int:
    spec = next(o for o in ORDERS if o.number == number)
    return sum(i.price_cents * i.qty for i in spec.items) + spec.shipping_cents - spec.discount_cents


def call(http: httpx.Client, method: str, path: str, **kwargs) -> dict:
    r = http.request(method, path, **kwargs)
    body = r.json()
    if r.status_code >= 400 or not body.get("status"):
        sys.exit(f"Paystack {method} {path} failed ({r.status_code}): {body.get('message')}")
    return body["data"]


def checkout() -> None:
    with client() as http:
        data = call(http, "POST", "/transaction/initialize", json={
            "email": payer_email(), "amount": paid_cents(FIRST_ORDER), "currency": currency(),
            "reference": f"harbor-{FIRST_ORDER.lower()}-{uuid.uuid4().hex[:10]}",
            "channels": ["card"], "metadata": {"order_number": FIRST_ORDER},
        })
    print(f"Pay for {FIRST_ORDER} in test mode here:\n  {data['authorization_url']}")
    print(f"Then run:\n  uv run python -m app.paystack_setup finish {data['reference']}")


def finish(reference: str) -> None:
    refs = payment_refs.load()
    with client() as http:
        tx = call(http, "GET", f"/transaction/verify/{reference}")
        if tx["status"] != "success":
            sys.exit(f"Payment {reference} is {tx['status']!r}, not success. Complete the checkout first.")
        auth = tx["authorization"]
        if not auth.get("reusable"):
            sys.exit("That card authorization is not reusable; pay with a different test card.")
        refs[FIRST_ORDER] = reference
        print(f"{FIRST_ORDER}: {reference} (checkout)")

        for spec in ORDERS:
            if spec.number in refs:
                continue
            ref = f"harbor-{spec.number.lower()}-{uuid.uuid4().hex[:10]}"
            charged = call(http, "POST", "/transaction/charge_authorization", json={
                "email": payer_email(), "amount": paid_cents(spec.number), "currency": currency(),
                "authorization_code": auth["authorization_code"], "reference": ref,
                "metadata": {"order_number": spec.number},
            })
            refs[spec.number] = charged["reference"]
            print(f"{spec.number}: {charged['reference']} ({charged['status']})")
            for cents, _, _ in spec.prior_refunds:  # keep Paystack consistent with seeded refund history
                call(http, "POST", "/refund", json={"transaction": charged["reference"], "amount": cents,
                                                    "merchant_note": "seeded prior refund"})
        payment_refs.save(refs)
    with Session(make_engine()) as s:
        print(f"Saved {len(refs)} references; applied to {payment_refs.apply_saved(s)} orders in the database.")


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "checkout":
        checkout()
    elif len(sys.argv) == 3 and sys.argv[1] == "finish":
        finish(sys.argv[2])
    else:
        sys.exit(__doc__)
