"""The interface every support agent implements, used by the chat API and the evals.

One agent instance holds one conversation. It is built against a session
factory, so evals can give each sample its own freshly seeded database.
"""

from __future__ import annotations

from typing import Protocol

from sqlalchemy.orm import Session, sessionmaker

AGENT_KINDS = ("trusted", "baseline", "stub")


class SupportAgent(Protocol):
    kind: str

    async def respond(self, message: str, image: tuple[str, str] | None = None) -> str:
        """image is (base64 data, mime type), already validated."""
        ...


class StubAgent:
    """Does nothing. Lets the eval suite run end to end before a real agent exists."""

    kind = "stub"

    def __init__(self, sessions: sessionmaker[Session]):
        self.sessions = sessions

    async def respond(self, message: str, image: tuple[str, str] | None = None) -> str:
        return "Sorry, I can't help with that yet."


def build_agent(kind: str, sessions: sessionmaker[Session]) -> SupportAgent:
    if kind == "stub":
        return StubAgent(sessions)
    if kind == "trusted":
        from app.graph import TrustedAgent

        return TrustedAgent(sessions)
    if kind == "baseline":
        from app.graph_baseline import BaselineAgent

        return BaselineAgent(sessions)
    raise ValueError(f"Unknown agent kind {kind!r}; expected one of {AGENT_KINDS}")
