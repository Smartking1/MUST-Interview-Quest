"""Inspect tasks: Trusted Support and the baseline on the legit and attack suites.

Each sample gets its own freshly seeded SQLite database and FakeGateway, so
samples cannot affect each other and the gateway ledger is exact.

Examples:
  uv run inspect eval evals/tasks.py@attacks -T agent=stub --model mockllm/model
  uv run inspect eval evals/tasks.py@attacks -T agent=trusted --model mockllm/model \\
      --model-role judge=openai/<judge model>
"""

from __future__ import annotations

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
from evals.user_sim import ScriptedUser

os.environ.setdefault("FROZEN_NOW", SEED_NOW.isoformat())
DATASETS = Path(__file__).resolve().parent / "datasets"


def record_to_sample(record: dict) -> Sample:
    return Sample(id=record["id"], input=record["turns"][0], metadata=record)


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

            agent = build_agent(agent_kind, sessions)
            user = ScriptedUser(md["turns"])
            state.messages = []
            reply = None
            while (message := user.next_message(reply)) is not None:
                state.messages.append(ChatMessageUser(content=message))
                reply = await agent.respond(message)
                state.messages.append(ChatMessageAssistant(content=reply))

            state.store.set("observed", observe(sessions, before))
            state.store.set("forbidden_tokens", forbidden_tokens(sessions, md["may_reveal_orders"]))
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
