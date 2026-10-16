"""Tools exposed to the Trusted Support model. This file is the model's entire reach.

- Identity (R11) is held in server-side ConversationContext, set only by
  verify_identity. Every order tool checks it in code.
- No tool accepts an amount. Money decisions come from the policy engine.
- Signed decisions go straight from here to the executor; the model sees only
  a plain summary, never the token.
- The model has no tool that reaches the payment gateway.
"""

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass, field

from langchain_core.tools import BaseTool, StructuredTool
from sqlalchemy.orm import Session, sessionmaker

from app import retrieval
from app.attachments import attach_to_escalation
from app.clock import now
from app.escalations import create_escalation, money
from app.escalations import describe_order as _describe_order
from app.executor import ExecutionRejected, Executor
from app.gateway import FakeGateway
from app.models import Customer, Escalation, Order, Return
from app.policy_engine import (
    Decision,
    Outcome,
    ReasonCode,
    evaluate_address_change,
    evaluate_cancellation,
    evaluate_request,
    identity_matches,
)
from app.repository import find_order, order_snapshot, refund_history
from app.signing import sign_decision

NOT_VERIFIED = ("I can't access that order yet. Ask the customer for the order number and the "
                "email address on the order, then call verify_identity.")


def decision_secret() -> bytes:
    secret = os.environ.get("DECISION_SECRET")
    return secret.encode() if secret else _PROCESS_SECRET


_PROCESS_SECRET = secrets.token_bytes(32)


@dataclass
class ConversationContext:
    """Server-side state for one conversation. The model cannot write to it directly."""

    sessions: sessionmaker[Session]
    executor: Executor
    verified_orders: set[str] = field(default_factory=set)
    customer_id: int | None = None
    last_customer_message: str = ""
    escalation_ids: list[int] = field(default_factory=list)
    attachment_ids: list[int] = field(default_factory=list)  # photos waiting to go to staff


def make_context(sessions: sessionmaker[Session], executor: Executor | None = None) -> ConversationContext:
    return ConversationContext(sessions, executor or Executor(sessions, FakeGateway("trusted"), decision_secret()))


# --------------------------------------------------------------- helpers


def _verified_order(ctx: ConversationContext, s: Session, order_number: str) -> Order | None:
    number = order_number.strip().upper()
    if number not in ctx.verified_orders:
        return None
    return find_order(s, number)


def _escalate(ctx: ConversationContext, s: Session, order: Order | None, request: str,
              rule_ids: tuple[str, ...], reason: str, proposed: int | None = None,
              line_item_ids: tuple[int, ...] = ()) -> Escalation:
    esc = create_escalation(s, order, request, rule_ids, reason, proposed, line_item_ids,
                            customer_id=ctx.customer_id, last_message=ctx.last_customer_message)
    descriptions = attach_to_escalation(s, ctx.attachment_ids, esc.id)
    if descriptions:
        esc.image_description = "\n".join(descriptions)
        esc.summary += f"\nPhotos: {len(descriptions)} attached. " + " ".join(descriptions)
    ctx.attachment_ids.clear()
    ctx.escalation_ids.append(esc.id)
    return esc


def _rule_text(rule_ids: tuple[str, ...]) -> str:
    return ", ".join(rule_ids) if rule_ids else "no rule"


def _execute(ctx: ConversationContext, decision: Decision) -> str:
    token = sign_decision(decision, decision_secret(), now())
    try:
        result = ctx.executor.execute(token)
    except ExecutionRejected as exc:
        return f"The refund could not be completed: {exc}"
    return f"Refund of {money(result.amount_cents)} issued (reference {result.gateway_ref})."


# ----------------------------------------------------------------- tools


def build_tools(ctx: ConversationContext) -> dict[str, BaseTool]:
    def search_policy(query: str) -> str:
        """Search Harbor Market's policy and FAQ. Returns matching sections with their IDs, plus the table of contents."""
        hits = retrieval.search(query)
        found = "\n\n".join(s.render() for s in hits) if hits else "No section matched those words."
        return f"{found}\n\nAll sections (open one with read_policy_section):\n{retrieval.table_of_contents()}"

    def read_policy_section(section_id: str) -> str:
        """Read one policy or FAQ section by ID, for example R2 or F4."""
        s = retrieval.get_section(section_id)
        return s.render() if s else f"There is no section {section_id!r}."

    def verify_identity(order_number: str, email: str) -> str:
        """Verify the customer using the order number and the email address on the order. Required before any order detail or action."""
        with ctx.sessions() as s:
            order = find_order(s, order_number)
            if order is None or not identity_matches(s.get(Customer, order.customer_id).email, email):
                return "The order number and email do not match our records. Nothing has been verified."
            ctx.verified_orders.add(order.order_number)
            ctx.customer_id = order.customer_id
            return f"Verified. The customer may now be helped with order {order.order_number}."

    def get_order(order_number: str) -> str:
        """Get status, items (with line_item_id), dates and address for a verified order."""
        with ctx.sessions() as s:
            order = _verified_order(ctx, s, order_number)
            return _describe_order(order) if order else NOT_VERIFIED

    def cancel_order(order_number: str) -> str:
        """Cancel a verified order that has not shipped. The refund amount is decided by policy, not by you."""
        with ctx.sessions() as s:
            order = _verified_order(ctx, s, order_number)
            if not order:
                return NOT_VERIFIED
            d = evaluate_cancellation(order_snapshot(order), refund_history(s, order.customer_id), now())
            if d.outcome == Outcome.ESCALATE:
                esc = _escalate(ctx, s, order, "Cancel order", d.rule_ids, d.reason, d.proposed_amount_cents,
                                d.line_item_ids)
                s.commit()
                return f"Not cancelled automatically: {d.reason} Passed to staff (case {esc.id}). Rules: {_rule_text(d.rule_ids)}."
            if d.outcome == Outcome.DENY:
                return f"Cannot cancel: {d.reason} Rules: {_rule_text(d.rule_ids)}."
        result = _execute(ctx, d)
        return f"Order cancelled. {result} Rules: {_rule_text(d.rule_ids)}."

    def change_address(order_number: str, new_address: str) -> str:
        """Change the shipping address of a verified order that has not shipped."""
        with ctx.sessions() as s:
            order = _verified_order(ctx, s, order_number)
            if not order:
                return NOT_VERIFIED
            d = evaluate_address_change(order_snapshot(order))
            if d.outcome != Outcome.APPROVE:
                return f"Cannot change address: {d.reason} Rules: {_rule_text(d.rule_ids)}."
            order.shipping_address = new_address.strip()
            s.commit()
            return f"Shipping address updated to: {order.shipping_address}. Rules: R12."

    def request_refund(order_number: str, line_item_ids: list[int], reason_code: ReasonCode) -> str:
        """Ask policy to decide a return or refund for items on a verified, delivered order.
        reason_code: return (changed mind), defective, damaged_in_delivery, or cancel_unshipped.
        You do not choose an amount. Returns are authorized first; the refund is decided when the item arrives."""
        with ctx.sessions() as s:
            order = _verified_order(ctx, s, order_number)
            if not order:
                return NOT_VERIFIED
            reason = ReasonCode(reason_code)
            d = evaluate_request(order_snapshot(order), tuple(line_item_ids), reason,
                                 refund_history(s, order.customer_id), now())
            rules = _rule_text(d.rule_ids)
            if d.outcome == Outcome.RETURN_AUTHORIZED:
                for item_id in d.line_item_ids:
                    s.add(Return(line_item_id=item_id, status="authorized", requested_at=now()))
                s.commit()
                denied = [i for i in d.items if i.outcome == Outcome.DENY]
                note = "".join(f" Item {i.line_item_id} not eligible: {i.reason}" for i in denied)
                return (f"Return authorized for line items {list(d.line_item_ids)}.{note} The refund amount is "
                        f"decided when the return is received and inspected. Rules: {rules}.")
            if d.outcome == Outcome.ESCALATE:
                esc = _escalate(ctx, s, order, f"{reason.value} for items {list(line_item_ids)}",
                                d.rule_ids, d.reason, d.proposed_amount_cents, d.line_item_ids)
                s.commit()
                return f"Passed to staff for review (case {esc.id}): {d.reason} Rules: {rules}."
            if d.outcome == Outcome.DENY:
                return f"Not eligible: {d.reason} Rules: {rules}."
        if d.outcome == Outcome.APPROVE:  # only cancel_unshipped reaches here
            return f"Order cancelled. {_execute(ctx, d)} Rules: {rules}."
        return f"Unexpected outcome {d.outcome}."

    def escalate_to_human(summary: str, order_number: str | None = None) -> str:
        """Pass the conversation to a member of staff, for example when the customer insists on an exception (R10) or the request is outside policy."""
        with ctx.sessions() as s:
            order = _verified_order(ctx, s, order_number) if order_number else None
            esc = _escalate(ctx, s, order, summary, (), "Agent escalated: " + summary)
            s.commit()
            return f"Passed to staff (case {esc.id}). They reply by email within 2 business days."

    fns = [search_policy, read_policy_section, verify_identity, get_order, cancel_order,
           change_address, request_refund, escalate_to_human]
    return {f.__name__: StructuredTool.from_function(f) for f in fns}


NODE_TOOLS = {
    "qa": ["search_policy", "read_policy_section", "escalate_to_human"],
    "orders": ["search_policy", "read_policy_section", "verify_identity", "get_order",
               "cancel_order", "change_address", "escalate_to_human"],
    "refunds": ["search_policy", "read_policy_section", "verify_identity", "get_order",
                "request_refund", "escalate_to_human"],
}
