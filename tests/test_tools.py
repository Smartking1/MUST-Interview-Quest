from sqlalchemy import func, select

from app.models import Escalation, GatewayLedger, Return
from app.repository import find_order
from app.tools import build_tools, make_context


def setup(sessions):
    ctx = make_context(sessions)
    return ctx, build_tools(ctx)


def run(tools, name, **args):
    return tools[name].invoke(args)


def ledger(sessions):
    with sessions() as s:
        return s.scalar(select(func.coalesce(func.sum(GatewayLedger.amount_kobo), 0)))


def test_order_tools_require_verification(sessions):
    ctx, t = setup(sessions)
    out = run(t, "get_order", order_number="HM-1025")
    assert "Gaming Console" not in out and "verify_identity" in out
    assert "verify_identity" in run(t, "cancel_order", order_number="HM-1001")
    assert "verify_identity" in run(t, "request_refund", order_number="HM-1005",
                                    line_item_ids=[1], reason_code="return")


def test_wrong_email_does_not_reveal_whether_order_exists(sessions):
    _, t = setup(sessions)
    real = run(t, "verify_identity", order_number="HM-1025", email="amara.okafor@example.com")
    fake = run(t, "verify_identity", order_number="HM-9999", email="amara.okafor@example.com")
    assert real == fake
    assert "do not match" in real


def test_verifying_one_order_does_not_unlock_another_customers(sessions):
    ctx, t = setup(sessions)
    assert "Verified" in run(t, "verify_identity", order_number="HM-1001", email="amara.okafor@example.com")
    assert "Gaming Console" not in run(t, "get_order", order_number="HM-1025")


def test_verification_is_case_insensitive_on_email_and_order(sessions):
    _, t = setup(sessions)
    assert "Verified" in run(t, "verify_identity", order_number="hm-1001", email="Amara.Okafor@Example.com ")


def test_cancel_unshipped_order_pays_full_amount_once(sessions):
    _, t = setup(sessions)
    run(t, "verify_identity", order_number="HM-1001", email="amara.okafor@example.com")
    out = run(t, "cancel_order", order_number="HM-1001")
    assert "₦48,500.00" in out
    assert "Cannot cancel" in run(t, "cancel_order", order_number="HM-1001")
    assert ledger(sessions) == 4_850_000


def test_cancel_over_limit_escalates_with_actionable_summary(sessions):
    ctx, t = setup(sessions)
    ctx.last_customer_message = "Please cancel HM-1002"
    run(t, "verify_identity", order_number="HM-1002", email="ben.carter@example.com")
    out = run(t, "cancel_order", order_number="HM-1002")
    assert "staff" in out and "R8" in out
    assert ledger(sessions) == 0
    with sessions() as s:
        esc = s.scalar(select(Escalation))
        for needle in ("Ben Carter", "HM-1002", "Espresso Machine", "R8", "₦423,500.00", "Please cancel HM-1002"):
            assert needle in esc.summary


def test_return_request_authorizes_and_pays_nothing(sessions):
    _, t = setup(sessions)
    run(t, "verify_identity", order_number="HM-1005", email="elena.rossi@example.com")
    with sessions() as s:
        item_id = find_order(s, "HM-1005").items[0].id
        before = s.scalar(select(func.count()).select_from(Return))
    out = run(t, "request_refund", order_number="HM-1005", line_item_ids=[item_id], reason_code="return")
    assert "Return authorized" in out
    assert ledger(sessions) == 0
    with sessions() as s:
        assert s.scalar(select(func.count()).select_from(Return)) == before + 1


def test_address_change_only_before_shipping(sessions):
    _, t = setup(sessions)
    run(t, "verify_identity", order_number="HM-1004", email="daniel.kim@example.com")
    assert "updated" in run(t, "change_address", order_number="HM-1004", new_address="5 Orchard Road")
    run(t, "verify_identity", order_number="HM-1003", email="chloe.martin@example.com")
    assert "Cannot change" in run(t, "change_address", order_number="HM-1003", new_address="99 Dock St")


def test_invalid_reason_code_is_rejected_by_schema(sessions):
    _, t = setup(sessions)
    run(t, "verify_identity", order_number="HM-1005", email="elena.rossi@example.com")
    try:
        out = run(t, "request_refund", order_number="HM-1005", line_item_ids=[1], reason_code="vip_exception")
    except Exception as exc:
        out = str(exc)
    assert "Return authorized" not in out
    assert ledger(sessions) == 0


def test_policy_search_returns_ids_and_table_of_contents(sessions):
    _, t = setup(sessions)
    out = run(t, "search_policy", query="Do you take PayPal?")
    assert "F4: Payment methods" in out
    assert "Visa" in run(t, "read_policy_section", section_id="F4")


def test_seeded_open_return_is_not_authorized_twice(sessions):
    """HM-1008 is seeded with an authorized return. Asking again creates nothing."""
    _, t = setup(sessions)
    run(t, "verify_identity", order_number="HM-1008", email="hiro.tanaka@example.com")
    with sessions() as s:
        item_id = find_order(s, "HM-1008").items[0].id
        before = s.scalar(select(func.count()).select_from(Return))
    out = run(t, "request_refund", order_number="HM-1008", line_item_ids=[item_id], reason_code="return")
    assert "already authorized" in out
    with sessions() as s:
        assert s.scalar(select(func.count()).select_from(Return)) == before
