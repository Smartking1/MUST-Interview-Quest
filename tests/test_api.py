"""API tests with no model: admin flows, and a clear error when no model is configured."""

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client(tmp_path, frozen_now, monkeypatch):
    monkeypatch.delenv("LLM_MODEL", raising=False)
    return TestClient(create_app(f"sqlite:///{tmp_path / 'api.db'}"))


def test_pages_served(client):
    assert client.get("/").status_code == 200
    assert client.get("/admin").status_code == 200


def test_chat_without_model_returns_clear_503(client):
    r = client.post("/api/chat", json={"message": "hi"})
    assert r.status_code == 503
    assert "LLM_MODEL" in r.json()["detail"]


def test_unknown_agent_rejected(client):
    assert client.post("/api/chat", json={"message": "hi", "agent": "god_mode"}).status_code == 400


def test_receiving_opened_return_refunds_with_restocking_fee(client):
    [ret] = client.get("/api/admin/returns").json()  # HM-1008 keyboard is seeded as authorized
    assert ret["order_number"] == "HM-1008"
    r = client.post(f"/api/admin/returns/{ret['id']}/receive", json={"opened": True})
    assert r.status_code == 200 and r.json()["amount_kobo"] == 10_200_000
    assert client.post(f"/api/admin/returns/{ret['id']}/receive", json={"opened": True}).status_code == 400
    [entry] = client.get("/api/admin/ledger").json()
    assert entry["amount"] == "₦102,000.00" and entry["agent"] == "trusted"


def test_human_approval_goes_through_executor_once(client, tmp_path):
    from app.db import make_engine, make_session_factory
    from app.tools import build_tools, make_context

    sessions = make_session_factory(make_engine(f"sqlite:///{tmp_path / 'api.db'}"))
    t = build_tools(make_context(sessions))
    t["verify_identity"].invoke({"order_number": "HM-1002", "email": "ben.carter@example.com"})
    assert "staff" in t["cancel_order"].invoke({"order_number": "HM-1002"})

    [esc] = client.get("/api/admin/escalations").json()
    assert "R8" in esc["rule_ids"] and esc["proposed_amount_kobo"] == 42_350_000
    assert client.post(f"/api/admin/escalations/{esc['id']}/approve", json={"admin": ""}).status_code == 400
    r = client.post(f"/api/admin/escalations/{esc['id']}/approve", json={"admin": "Kingsley"})
    assert r.status_code == 200 and r.json()["amount_kobo"] == 42_350_000
    assert client.post(f"/api/admin/escalations/{esc['id']}/approve", json={"admin": "Kingsley"}).status_code == 400
    assert client.get("/api/admin/escalations").json() == []


def test_human_cannot_pay_more_than_paid(client, tmp_path):
    from app.db import make_engine, make_session_factory
    from app.tools import build_tools, make_context

    sessions = make_session_factory(make_engine(f"sqlite:///{tmp_path / 'api.db'}"))
    t = build_tools(make_context(sessions))
    t["verify_identity"].invoke({"order_number": "HM-1011", "email": "amara.okafor@example.com"})
    out = t["get_order"].invoke({"order_number": "HM-1011"})
    item = int(out.split("line_item_id ")[1].split(":")[0])
    t["request_refund"].invoke({"order_number": "HM-1011", "line_item_ids": [item], "reason_code": "defective"})
    [esc] = client.get("/api/admin/escalations").json()
    r = client.post(f"/api/admin/escalations/{esc['id']}/approve", json={"admin": "K", "amount_kobo": 100_000_000})
    assert r.status_code == 400 and "R7" in r.json()["detail"]
    assert client.get("/api/admin/ledger").json() == []


def test_saved_payment_refs_survive_a_demo_reset(tmp_path, frozen_now, monkeypatch):
    import json

    from app.db import make_engine, make_session_factory
    from app.repository import find_order

    refs = tmp_path / "refs.json"
    refs.write_text(json.dumps({"HM-1005": "harbor-hm-1005-abc"}))
    monkeypatch.setenv("PAYMENT_REFS_FILE", str(refs))
    url = f"sqlite:///{tmp_path / 'refs.db'}"
    client = TestClient(create_app(url))
    client.post("/api/admin/reset")
    with make_session_factory(make_engine(url))() as s:
        assert find_order(s, "HM-1005").gateway_payment_ref == "harbor-hm-1005-abc"
