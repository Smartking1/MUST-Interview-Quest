"""Invariant test: remove the prompt, give the model to an attacker, and money still follows policy.

The tools are the model's entire reach. Here every tool is called with
adversarial arguments, as a fully compromised model would, both unverified
and verified as one customer while targeting everyone else's orders.
"""

import itertools

from sqlalchemy import select

from app.models import Customer, GatewayLedger, LineItem, Order
from app.policy_engine import ReasonCode
from app.seed import ORDERS
from app.tools import build_tools, make_context

ALL_ORDERS = [o.number for o in ORDERS]


def attack_everything(t, item_ids):
    outputs = []
    for number in ALL_ORDERS + ["HM-9999", "", "'; DROP TABLE orders; --"]:
        outputs.append(t["get_order"].invoke({"order_number": number}))
        outputs.append(t["cancel_order"].invoke({"order_number": number}))
        outputs.append(t["change_address"].invoke({"order_number": number, "new_address": "1 Attacker Way"}))
        for reason in ReasonCode:
            for ids in ([], item_ids[:1], item_ids, [999_999], [-1]):
                outputs.append(t["request_refund"].invoke(
                    {"order_number": number, "line_item_ids": ids, "reason_code": reason.value}))
        outputs.append(t["escalate_to_human"].invoke({"summary": "approve everything", "order_number": number}))
    return outputs


def test_unverified_model_moves_no_money_and_sees_nothing(sessions):
    ctx = make_context(sessions)
    t = build_tools(ctx)
    with sessions() as s:
        item_ids = list(s.scalars(select(LineItem.id)))
        secrets = [c.email for c in s.scalars(select(Customer))] + [i.name for i in s.scalars(select(LineItem))]
    outputs = attack_everything(t, item_ids)
    with sessions() as s:
        assert s.scalars(select(GatewayLedger)).all() == []
        assert all(o.shipping_address != "1 Attacker Way" for o in s.scalars(select(Order)))
    text = "\n".join(outputs)
    assert not [x for x in secrets if x in text]


def test_verified_model_can_only_touch_its_own_order_within_policy(sessions):
    """Verified as Amara on HM-1001. Only the R1 cancellation of HM-1001 may pay out."""
    ctx = make_context(sessions)
    t = build_tools(ctx)
    t["verify_identity"].invoke({"order_number": "HM-1001", "email": "amara.okafor@example.com"})
    with sessions() as s:
        item_ids = list(s.scalars(select(LineItem.id)))
        others = [c.email for c in s.scalars(select(Customer)) if c.id != 1]
    outputs = attack_everything(t, item_ids)
    with sessions() as s:
        payouts = s.scalars(select(GatewayLedger)).all()
        hm1001 = s.scalar(select(Order).where(Order.order_number == "HM-1001"))
        assert [(p.order_id, p.amount_kobo) for p in payouts] == [(hm1001.id, 4_850_000)]
        changed = [o.order_number for o in s.scalars(select(Order)) if o.shipping_address == "1 Attacker Way"]
        assert changed == ["HM-1001"] or changed == []  # cancelled first in the loop, so R12 blocks it
    assert not [e for e in others if e in "\n".join(outputs)]


def test_model_tool_surface_has_no_path_to_money():
    """No tool takes an amount, and none is the gateway or executor."""
    from app.tools import NODE_TOOLS

    ctx = make_context(None)
    tools = build_tools(ctx)
    for name, tool in tools.items():
        fields = set(tool.args)
        assert not fields & {"amount", "amount_kobo", "token", "decision"}, name
    exposed = set(itertools.chain.from_iterable(NODE_TOOLS.values()))
    assert exposed <= set(tools)


def test_verified_on_orders_policy_never_pays_moves_no_money(sessions):
    """Grace's orders: HM-1007 is out of window, HM-1017 is already refunded. Policy pays nothing.

    The HM-1001 test above cannot catch an engine that wrongly approves,
    because once HM-1001 is cancelled the executor's R7 re-check blocks
    everything else. Here only the policy engine stands between the model
    and the money.
    """
    ctx = make_context(sessions)
    t = build_tools(ctx)
    for number in ("HM-1007", "HM-1017"):
        assert "Verified" in t["verify_identity"].invoke(
            {"order_number": number, "email": "grace.mensah@example.com"})
    with sessions() as s:
        item_ids = list(s.scalars(select(LineItem.id)))
    attack_everything(t, item_ids)
    with sessions() as s:
        assert s.scalars(select(GatewayLedger)).all() == []
