"""Database engine and sessions. DATABASE_URL defaults to a local SQLite file."""

from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.models import Base


def make_engine(url: str | None = None) -> Engine:
    return create_engine(url or os.environ.get("DATABASE_URL", "sqlite:///harbor.db"))


def init_db(engine: Engine) -> None:
    Base.metadata.create_all(engine)


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(engine, expire_on_commit=False)
