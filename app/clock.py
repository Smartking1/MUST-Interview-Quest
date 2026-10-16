"""Single source of the current time. FROZEN_NOW pins it for evals and demos."""

from __future__ import annotations

import os
from datetime import UTC, datetime


def now() -> datetime:
    frozen = os.environ.get("FROZEN_NOW")
    if frozen:
        return as_utc(datetime.fromisoformat(frozen))
    return datetime.now(UTC)


def as_utc(dt: datetime) -> datetime:
    """SQLite drops timezone info; every stored time is UTC."""
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)
