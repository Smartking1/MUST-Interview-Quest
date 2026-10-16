"""FastAPI app: customer chat, staff admin, static pages.

Run: uv run uvicorn app.main:create_app --factory --reload
No auth system by design (directive section 12): /admin asks for a name so
every staff decision is attributable, and that is all.
"""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import inspect as sa_inspect
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import admin, payment_refs
from app.attachments import AttachmentError
from app.attachments import validate as validate_image
from app.clock import now
from app.agent_api import SupportAgent
from app.db import init_db, make_engine, make_session_factory
from app.escalations import money
from app.executor import Executor
from app.gateway import gateway_from_env
from app.llm import ModelNotConfigured
from app.models import Attachment, Base, Customer, GatewayLedger, LineItem, Order
from app.seed import seed
from app.tools import decision_secret

STATIC = Path(__file__).resolve().parent / "static"


class ChatIn(BaseModel):
    message: str
    agent: str = "trusted"
    conversation_id: str | None = None
    image_base64: str | None = None
    image_mime: str | None = None


class ApproveIn(BaseModel):
    admin: str
    amount_kobo: int | None = None


class DenyIn(BaseModel):
    admin: str


class ReceiveIn(BaseModel):
    opened: bool
    tags_attached: bool = False


def create_app(db_url: str | None = None) -> FastAPI:
    engine = make_engine(db_url)
    if not sa_inspect(engine).has_table("orders"):
        init_db(engine)
        with Session(engine) as s:
            seed(s, now())  # demo: seed relative to the real clock so dates read naturally
            payment_refs.apply_saved(s)
    sessions = make_session_factory(engine)
    secret = decision_secret()
    executor = Executor(sessions, gateway_from_env(), secret)
    conversations: dict[str, SupportAgent] = {}

    app = FastAPI(title="Trusted Support")

    def new_agent(kind: str) -> SupportAgent:
        if kind == "trusted":
            from app.graph import TrustedAgent

            return TrustedAgent(sessions, executor=executor)
        if kind == "baseline":
            from app.graph_baseline import BaselineAgent

            return BaselineAgent(sessions)
        raise HTTPException(400, "agent must be 'trusted' or 'baseline'")

    @app.get("/")
    def index():
        return FileResponse(STATIC / "index.html")

    @app.get("/admin")
    def admin_page():
        return FileResponse(STATIC / "admin.html")

    @app.post("/api/chat")
    async def chat(body: ChatIn):
        cid = body.conversation_id or uuid.uuid4().hex
        key = f"{body.agent}:{cid}"
        if key not in conversations:
            try:
                conversations[key] = new_agent(body.agent)
            except ModelNotConfigured as exc:
                raise HTTPException(503, str(exc)) from exc
        image = None
        if body.image_base64:
            try:
                validate_image(body.image_base64, body.image_mime or "")
            except AttachmentError as exc:
                raise HTTPException(400, str(exc)) from exc
            image = (body.image_base64, body.image_mime)
        reply = await conversations[key].respond(body.message, image)
        return {"conversation_id": cid, "agent": body.agent, "reply": reply}

    @app.get("/api/admin/escalations")
    def escalations():
        with sessions() as s:
            return [{"id": e.id, "summary": e.summary, "rule_ids": e.rule_ids, "reason": e.reason,
                     "proposed_amount_kobo": e.proposed_amount_kobo, "created_at": e.created_at.isoformat(),
                     "attachments": list(s.scalars(select(Attachment.id).where(Attachment.escalation_id == e.id)))}
                    for e in admin.open_escalations(s)]

    @app.get("/api/admin/attachments/{attachment_id}")
    def attachment(attachment_id: int):
        with sessions() as s:
            att = s.get(Attachment, attachment_id)
            if att is None or att.escalation_id is None:
                raise HTTPException(404, "Not found")
            return FileResponse(att.path, media_type=att.mime)

    @app.post("/api/admin/escalations/{escalation_id}/approve")
    def approve(escalation_id: int, body: ApproveIn):
        try:
            r = admin.approve_escalation(sessions, executor, secret, escalation_id, body.admin, body.amount_kobo)
        except admin.AdminError as exc:
            raise HTTPException(400, str(exc)) from exc
        return {"message": r.message, "amount_kobo": r.amount_kobo}

    @app.post("/api/admin/escalations/{escalation_id}/deny")
    def deny(escalation_id: int, body: DenyIn):
        try:
            return {"message": admin.deny_escalation(sessions, escalation_id, body.admin).message}
        except admin.AdminError as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.get("/api/admin/returns")
    def returns():
        with sessions() as s:
            out = []
            for r in admin.pending_returns(s):
                item = s.get(LineItem, r.line_item_id)
                order = s.get(Order, item.order_id)
                out.append({"id": r.id, "order_number": order.order_number, "item": item.name,
                            "category": item.category, "price": money(item.price_kobo * item.qty),
                            "requested_at": r.requested_at.isoformat()})
            return out

    @app.post("/api/admin/returns/{return_id}/receive")
    def receive(return_id: int, body: ReceiveIn):
        try:
            r = admin.receive_return(sessions, executor, secret, return_id, body.opened, body.tags_attached)
        except admin.AdminError as exc:
            raise HTTPException(400, str(exc)) from exc
        return {"message": r.message, "amount_kobo": r.amount_kobo}

    @app.get("/api/admin/ledger")
    def ledger():
        with sessions() as s:
            rows = s.scalars(select(GatewayLedger).order_by(GatewayLedger.id.desc()).limit(50))
            orders = {o.id: o.order_number for o in s.scalars(select(Order))}
            return [{"agent": g.agent, "order_number": orders.get(g.order_id), "amount": money(g.amount_kobo),
                     "gateway": g.gateway, "ref": g.gateway_ref, "at": g.created_at.isoformat()} for g in rows]

    @app.get("/api/demo/customers")
    def demo_customers():
        """Fictional seeded customers, listed so a demo viewer knows what to type."""
        with sessions() as s:
            return [{"order_number": o.order_number, "email": s.get(Customer, o.customer_id).email,
                     "status": o.status} for o in s.scalars(select(Order).order_by(Order.id))]

    @app.post("/api/admin/reset")
    def reset():
        Base.metadata.drop_all(engine)
        init_db(engine)
        with Session(engine) as s:
            seed(s, now())
            payment_refs.apply_saved(s)
        conversations.clear()
        return {"message": "Database reset to seed data."}

    return app

