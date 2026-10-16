import pytest
from sqlalchemy.orm import Session

from app.db import init_db, make_engine, make_session_factory
from app.seed import SEED_NOW, seed


@pytest.fixture
def frozen_now(monkeypatch):
    monkeypatch.setenv("FROZEN_NOW", SEED_NOW.isoformat())
    return SEED_NOW


@pytest.fixture
def sessions(tmp_path, frozen_now):
    """A freshly seeded database per test, with the clock pinned to SEED_NOW."""
    engine = make_engine(f"sqlite:///{tmp_path / 'test.db'}")
    init_db(engine)
    with Session(engine) as s:
        seed(s)
    return make_session_factory(engine)
