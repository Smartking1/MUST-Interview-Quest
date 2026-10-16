"""Inspect tasks: Trusted Support and the baseline on the legit and attack suites.

Each sample gets its own freshly seeded SQLite database and FakeGateway, so
samples cannot affect each other and the gateway ledger is exact.

Examples:
  uv run inspect eval evals/tasks.py@attacks -T agent=stub --model mockllm/model
  uv run inspect eval evals/tasks.py@attacks -T agent=trusted --model mockllm/model \\
      --model-role judge=openai/<judge model>
"""

from __future__ import annotations

import base64
import os
import tempfile
from pathlib import Path

from inspect_ai import Task, task
from inspect_ai.dataset import Sample, json_dataset
from inspect_ai.model import ChatMessageAssistant, ChatMessageUser, ModelOutput
from inspect_ai.solver import Generate, TaskState, solver
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.agent_api import build_agent
from app.db import init_db, make_engine, make_session_factory
from app.models import Customer, Escalation, GatewayLedger, LineItem, Order, Refund, Return
from app.seed import SEED_NOW, seed
from evals.scorers import (
    data_leak,
    naira_given_away,
    invented_policy,
    outcome_match,
    unauthorized_refund,
)
from evals.attacker import AdaptiveAttacker
from evals.user_sim import ScriptedUser

os.environ.setdefault("FROZEN_NOW", SEED_NOW.isoformat())
DATASETS = Path(__file__).resolve().parent / "datasets"


EVALS_DIR = Path(__file__).resolve().parent


def record_to_sample(record: dict) -> Sample:
    first = record["turns"][0] if record.get("turns") else record["goal"]
    return Sample(id=record["id"], input=first if isinstance(first, str) else first["text"], metadata=record)


def load_image(path: str) -> tuple[str, str]:
    data = (EVALS_DIR / path).read_bytes()
    return base64.b64encode(data).decode(), "image/png"


def make_user(md: dict):
    if md.get("goal"):
        return AdaptiveAttacker(md["goal"], md["persona"], md.get("max_turns", 8))
    return ScriptedUser(md["turns"])


def snapshot(sessions: sessionmaker[Session]) -> dict:
    with sessions() as s:
        return {
            "returns": s.scalar(select(func.count()).select_from(Return)),
            "addresses": dict(s.execute(select(Order.order_number, Order.shipping_address)).all()),
            "statuses": dict(s.execute(select(Order.order_number, Order.status)).all()),
        }


def observe(sessions: sessionmaker[Session], before: dict) -> dict:
    """What actually changed in the database during the conversation."""
    after = snapshot(sessions)
    with sessions() as s:
        ledger = s.scalar(select(func.coalesce(func.sum(GatewayLedger.amount_kobo), 0)))
        refunds = s.scalar(select(func.count()).select_from(Refund).where(Refund.issuer != "seed"))
        escalations = s.scalar(select(func.count()).select_from(Escalation))
    effects = []
    if refunds:
        effects.append("refund")
    if any(after["statuses"][n] == "cancelled" != before["statuses"][n] for n in after["statuses"]):
        effects.append("cancel")
    if after["returns"] > before["returns"]:
        effects.append("return_authorized")
    if after["addresses"] != before["addresses"]:
        effects.append("address_change")
    if escalations:
        effects.append("escalation")
    return {"ledger_kobo": int(ledger), "effects": effects}


def forbidden_tokens(sessions: sessionmaker[Session], may_reveal: list[str]) -> list[str]:
    """Identifying data of every order the customer may not see, minus anything on allowed orders."""
    with sessions() as s:
        orders = s.scalars(select(Order)).all()
        allowed, forbidden = set(), set()
        for o in orders:
            cust = s.get(Customer, o.customer_id)
            tokens = {o.order_number, cust.email, cust.name, o.shipping_address}
            tokens |= {i.name for i in s.scalars(select(LineItem).where(LineItem.order_id == o.id))}
            (allowed if o.order_number in may_reveal else forbidden).update(tokens)
    return sorted(forbidden - allowed)


@solver
def run_conversation(agent_kind: str):
    async def solve(state: TaskState, generate: Generate) -> TaskState:
        md = state.metadata
        with tempfile.TemporaryDirectory() as tmp:
            engine = make_engine(f"sqlite:///{tmp}/sample.db")
            init_db(engine)
            with Session(engine) as s:
                seed(s)
            sessions = make_session_factory(engine)
            before = snapshot(sessions)
            # From the seeded state: a customer's own old address must not count as a leak after they change it
            forbidden = forbidden_tokens(sessions, md["may_reveal_orders"])

            agent = build_agent(agent_kind, sessions)
            user = make_user(md)
            state.messages = []
            actions: list[str] = []  # tool results, so the judge can tell reported actions from invented ones
            reply = None
            while (turn := await user.next_message(reply)) is not None:
                message = turn if isinstance(turn, str) else turn["text"]
                image = load_image(turn["image"]) if isinstance(turn, dict) and turn.get("image") else None
                shown = message + (f"\n[photo attached: {turn['image']}]" if image else "")
                state.messages.append(ChatMessageUser(content=shown))
                seen = len(getattr(agent, "messages", []))
                reply = await agent.respond(message, image)
                state.messages.append(ChatMessageAssistant(content=reply))
                actions += [m.text for m in getattr(agent, "messages", [])[seen:] if m.type == "tool"]
            state.store.set("actions", actions)
            state.store.set("guard_events", list(getattr(agent, "guard_events", [])))

            state.store.set("observed", observe(sessions, before))
            state.store.set("forbidden_tokens", forbidden)
            engine.dispose()
        state.output = ModelOutput.from_content(model=agent_kind, content=reply or "")
        return state

    return solve


def _task(dataset: str, agent: str, judge: bool | None) -> Task:
    scorers = [unauthorized_refund(), naira_given_away(), outcome_match(), data_leak()]
    if judge if judge is not None else agent != "stub":
        scorers.append(invented_policy())
    return Task(
        dataset=json_dataset(str(DATASETS / f"{dataset}.jsonl"), record_to_sample),
        solver=run_conversation(agent),
        scorer=scorers,
        metadata={"agent": agent, "dataset": dataset},
    )


@task
def legit(agent: str = "trusted", judge: bool | None = None) -> Task:
    return _task("legit", agent, judge)


@task
def attacks(agent: str = "trusted", judge: bool | None = None) -> Task:
    return _task("attacks", agent, judge)


@task
def adaptive(agent: str = "trusted", judge: bool | None = None) -> Task:
    """Day 4: an attacker model with a goal, up to 8 adaptive turns. Needs --model-role attacker=..."""
    return _task("adaptive", agent, judge)
