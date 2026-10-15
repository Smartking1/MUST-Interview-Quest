"""HMAC signing of money decisions (architecture invariant 3).

A signed decision carries everything the executor needs, so the executor
never trusts anything else. The executor rejects unsigned, altered, expired
or reused decisions; reuse is enforced there with decision_id as the key.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta

from app.policy_engine import Decision, Outcome

DEFAULT_TTL = timedelta(minutes=15)


class InvalidDecision(Exception):
    pass


@dataclass(frozen=True)
class SignedPayload:
    decision_id: str
    order_id: int
    line_item_ids: tuple[int, ...]
    amount_cents: int
    rule_ids: tuple[str, ...]
    issuer: str  # "policy_engine" or "human:<name>"
    issued_at: str  # ISO 8601, UTC
    expires_at: str


def _canonical(payload: SignedPayload) -> bytes:
    return json.dumps(asdict(payload), sort_keys=True, separators=(",", ":")).encode()


def _mac(secret: bytes, body: bytes) -> str:
    return hmac.new(secret, body, hashlib.sha256).hexdigest()


def sign(payload: SignedPayload, secret: bytes) -> str:
    body = _canonical(payload)
    return base64.urlsafe_b64encode(body).decode() + "." + _mac(secret, body)


def sign_decision(
    decision: Decision,
    secret: bytes,
    now: datetime,
    issuer: str = "policy_engine",
    ttl: timedelta = DEFAULT_TTL,
) -> str:
    """Sign an APPROVE decision. Nothing else can be turned into money."""
    if decision.outcome != Outcome.APPROVE or decision.amount_cents <= 0:
        raise InvalidDecision("Only approved decisions with a positive amount can be signed.")
    payload = SignedPayload(
        decision_id=str(uuid.uuid4()),
        order_id=decision.order_id,
        line_item_ids=tuple(decision.line_item_ids),
        amount_cents=decision.amount_cents,
        rule_ids=tuple(decision.rule_ids),
        issuer=issuer,
        issued_at=now.isoformat(),
        expires_at=(now + ttl).isoformat(),
    )
    return sign(payload, secret)


def verify(token: str, secret: bytes, now: datetime) -> SignedPayload:
    """Return the payload if the signature is valid and unexpired, else raise."""
    try:
        encoded, mac = token.split(".", 1)
        body = base64.urlsafe_b64decode(encoded.encode())
    except (ValueError, TypeError) as exc:
        raise InvalidDecision("Malformed decision token.") from exc
    if not hmac.compare_digest(_mac(secret, body), mac):
        raise InvalidDecision("Signature does not match.")
    data = json.loads(body)
    payload = SignedPayload(
        **{**data, "line_item_ids": tuple(data["line_item_ids"]), "rule_ids": tuple(data["rule_ids"])}
    )
    if now >= datetime.fromisoformat(payload.expires_at):
        raise InvalidDecision("Decision has expired.")
    return payload
