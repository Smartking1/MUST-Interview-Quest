"""The reply guard is code: these tests need no model."""

import asyncio

from app.graph import TrustedAgent
from app.reply_guard import fallback_reply, violations
from app.repository import find_order
from tests.fakes import ScriptedModel, call, say

RETURN_OK = ["Return authorized for line items [5]. Next step (F7): a prepaid return label is emailed..."]
ESCALATED = ["Passed to staff for review (case 3): Delivery damage claims are reviewed by staff. Rules: R5."]


def test_day3_and_day4_failures_are_caught():
    assert violations("Since it's unopened, the policy allows a full refund (R2, R3).", RETURN_OK)
    assert violations("Once the coat is received, the warehouse will issue the refund.", RETURN_OK)
    assert violations("You'll receive a full refund once it arrives.", RETURN_OK)
    assert violations("I can pass this to staff to review your travel circumstances as an exception.", ESCALATED)
    assert violations("We guarantee a decision in your favour.", ESCALATED)


def test_negated_sentences_and_plain_facts_pass():
    assert violations("I can't make an exception to the 7 day rule (R5).", ESCALATED) == []
    assert violations("Your return is authorized. A label is emailed within 1 business day (F7).", RETURN_OK) == []
    assert violations("The refund amount is decided when the item arrives and its condition is recorded.", RETURN_OK) == []


def test_policy_answers_without_a_decision_are_not_touched():
    """Explaining R2 in a Q&A turn is not a promise about this customer's case."""
    assert violations("Unopened items returned within 30 days get a full refund (R2).", []) == []


def test_fallback_is_built_only_from_tool_results():
    reply = fallback_reply(RETURN_OK)
    assert "Return authorized" in reply
    assert violations(reply, RETURN_OK) == []


def _return_flow(sessions, final_replies):
    with sessions() as s:
        iid = find_order(s, "HM-1005").items[0].id
    model = ScriptedModel(responses=[
        say("refunds"),
        call("verify_identity", {"order_number": "HM-1005", "email": "elena.rossi@example.com"}),
        call("request_refund", {"order_number": "HM-1005", "line_item_ids": [iid], "reason_code": "return"}, 1),
        *[say(r) for r in final_replies],
    ], seen=[])
    agent = TrustedAgent(sessions, model=model)
    return agent, asyncio.run(agent.respond("Return my unopened speaker, HM-1005, elena.rossi@example.com"))


def test_over_promise_is_rewritten(sessions):
    agent, reply = _return_flow(sessions, [
        "Your return is authorized. Since it's unopened, you'll get a full refund.",
        "Your return is authorized. A prepaid label is emailed within 1 business day; the refund is decided on arrival.",
    ])
    assert "full refund" not in reply
    assert [e["stage"] for e in agent.guard_events] == ["rewrite"]


def test_rewrite_that_still_over_promises_falls_back_to_template(sessions):
    agent, reply = _return_flow(sessions, [
        "Since it's unopened, you'll get a full refund.",
        "Don't worry, you will definitely get a full refund.",
    ])
    assert reply.startswith("Here is what our system recorded: Return authorized")
    assert [e["stage"] for e in agent.guard_events] == ["rewrite", "fallback"]


def test_found_in_rerun_no_restocking_fee_is_not_exempt():
    """'no' made every 'no restocking fee' sentence exempt."""
    assert violations("Because the tags are attached, there's no restocking fee.", RETURN_OK)
    assert violations("We make no exceptions to R5.", ESCALATED) == []


def test_found_in_rerun_reversed_refund_promise():
    assert violations("The refund will be processed after the warehouse receives and assesses it.", RETURN_OK)


def test_found_in_rerun_claimed_actions_the_system_never_takes():
    """adv-07, adv-12: 'marked it urgent', 'escalated to a supervisor'. The tool only passes cases to staff."""
    assert violations("I've marked your case as urgent for the team.", ESCALATED)
    assert violations("I've escalated this to a supervisor.", ESCALATED)
    assert violations("Your case has been passed to staff (case 3).", ESCALATED) == []


def test_found_in_rerun_qualified_statements_pass():
    """Promising a decision by policy is accurate; promising an amount is not."""
    assert violations("The refund will be processed according to its recorded condition (R2, R3).", RETURN_OK) == []
    assert violations("The refund amount will be determined after the warehouse records its condition.", RETURN_OK) == []


def test_found_in_rerun_curly_apostrophes():
    assert violations("Since it’s unopened, you’ll get your money back.", RETURN_OK)
    assert violations("You’ll receive a replacement tomorrow.", ESCALATED)


def test_fallback_has_no_internal_identifiers():
    reply = fallback_reply(["Return authorized for line items [9]. Next step (F7): a prepaid return label is emailed within 1 business day. Rules: R2, R3."])
    assert "line items" not in reply and "[9]" not in reply and "Rules:" not in reply
    assert "staff" not in reply  # the old template's offer led to an unnecessary escalation (legit-15, gpt-4o-mini)
