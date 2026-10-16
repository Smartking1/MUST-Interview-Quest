import base64
import json
from datetime import UTC, datetime, timedelta

import pytest

from app.policy_engine import Decision, Outcome
from app.signing import InvalidDecision, sign_decision, verify

SECRET = b"test-secret"
NOW = datetime(2026, 10, 15, 12, 0, tzinfo=UTC)
APPROVED = Decision(Outcome.APPROVE, 100, (1,), ("R2",), "ok", amount_kobo=5_000)


def test_round_trip():
    payload = verify(sign_decision(APPROVED, SECRET, NOW), SECRET, NOW)
    assert payload.amount_kobo == 5_000
    assert payload.order_id == 100
    assert payload.issuer == "policy_engine"


def test_each_decision_gets_a_unique_id():
    a = verify(sign_decision(APPROVED, SECRET, NOW), SECRET, NOW)
    b = verify(sign_decision(APPROVED, SECRET, NOW), SECRET, NOW)
    assert a.decision_id != b.decision_id


@pytest.mark.parametrize("outcome", [Outcome.DENY, Outcome.ESCALATE, Outcome.RETURN_AUTHORIZED])
def test_non_approve_decisions_cannot_be_signed(outcome):
    with pytest.raises(InvalidDecision):
        sign_decision(Decision(outcome, 100, (1,), ("R4",), "x"), SECRET, NOW)


def test_altered_amount_is_rejected():
    encoded, mac = sign_decision(APPROVED, SECRET, NOW).split(".")
    body = json.loads(base64.urlsafe_b64decode(encoded))
    body["amount_kobo"] = 500_000
    forged = base64.urlsafe_b64encode(json.dumps(body).encode()).decode() + "." + mac
    with pytest.raises(InvalidDecision):
        verify(forged, SECRET, NOW)


def test_wrong_secret_is_rejected():
    with pytest.raises(InvalidDecision):
        verify(sign_decision(APPROVED, SECRET, NOW), b"other", NOW)


def test_expired_decision_is_rejected():
    token = sign_decision(APPROVED, SECRET, NOW)
    with pytest.raises(InvalidDecision):
        verify(token, SECRET, NOW + timedelta(minutes=15))


@pytest.mark.parametrize("token", ["", "garbage", "a.b", "!!!.deadbeef"])
def test_malformed_tokens_are_rejected(token):
    with pytest.raises(InvalidDecision):
        verify(token, SECRET, NOW)
