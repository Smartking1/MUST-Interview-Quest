"""Gateway payment references for seeded orders, kept outside the database.

Test-mode payments are made once (app.paystack_setup), but the demo database
is reset often. References live in PAYMENT_REFS_FILE and are re-applied after
every seed.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Order


def refs_file() -> Path:
    return Path(os.environ.get("PAYMENT_REFS_FILE", ".payment_refs.json"))


def load() -> dict[str, str]:
    path = refs_file()
    return json.loads(path.read_text()) if path.exists() else {}


def save(refs: dict[str, str]) -> None:
    refs_file().write_text(json.dumps(refs, indent=2, sort_keys=True))


def apply_saved(session: Session) -> int:
    refs = load()
    applied = 0
    refs = {k: v for k, v in refs.items() if not k.startswith("_")}  # skip metadata such as the auth code
    for order in session.scalars(select(Order).where(Order.order_number.in_(refs))):
        order.gateway_payment_ref = refs[order.order_number]
        applied += 1
    session.commit()
    return applied
