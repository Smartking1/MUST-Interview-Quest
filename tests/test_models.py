from app.db import init_db, make_engine
from app.models import Base


def test_schema_creates_in_memory():
    engine = make_engine("sqlite://")
    init_db(engine)
    assert {"customers", "orders", "line_items", "returns", "refunds",
            "escalations", "gateway_ledger"} <= set(Base.metadata.tables)
