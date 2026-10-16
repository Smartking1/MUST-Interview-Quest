"""Scripted user simulator (Days 1 to 3).

Plays the sample's turns in order regardless of the agent's replies. The
Day 4 adaptive attacker (attacker.py) replaces this with a model that adapts.
"""

from __future__ import annotations


class ScriptedUser:
    """Turns are plain text, or {"text": ..., "image": "<path under evals/>"} for a photo."""

    def __init__(self, turns: list):
        self._turns = list(turns)
        self._i = 0

    async def next_message(self, last_reply: str | None):
        if self._i >= len(self._turns):
            return None
        msg = self._turns[self._i]
        self._i += 1
        return msg
