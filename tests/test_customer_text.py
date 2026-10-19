"""Rule codes (R1 to R12, F1 to F8) are internal. Customers never see them, from either agent."""

import pytest

from app.customer_text import hide_rule_codes, shows_rule_code

# Phrasings taken from real agent replies in the eval logs
CASES = [
    ("Unopened items can be returned within 30 days of delivery for a full refund. **(R2)**",
     "Unopened items can be returned within 30 days of delivery for a full refund."),
    ("Your return is authorized. A prepaid label is emailed within 1 business day (F7).",
     "Your return is authorized. A prepaid label is emailed within 1 business day."),
    ("The refund will be processed according to its recorded condition (R2, R3).",
     "The refund will be processed according to its recorded condition."),
    ("I can't issue it because refunds over ₦300,000 require human approval under **R8**.",
     "I can't issue it because refunds over ₦300,000 require human approval under our policy."),
    ("Order HM-1001 was cancelled. This follows policy **R12**.",
     "Order HM-1001 was cancelled. This follows our policy."),
    ("Under R4, defective items are reviewed by staff.",
     "Under our policy, defective items are reviewed by staff."),
    ("Rules: R1, R8.", ""),
    ("Passed to staff under case 1 (R1, R8).", "Passed to staff under case 1."),
    ("Final-sale items aren't refundable under **R6**, and seller promises aren't honored (**R10**).",
     "Final-sale items aren't refundable under our policy, and seller promises aren't honored."),
]


@pytest.mark.parametrize("raw,clean", CASES)
def test_rule_codes_are_removed_cleanly(raw, clean):
    assert hide_rule_codes(raw) == clean
    assert not shows_rule_code(hide_rule_codes(raw))


@pytest.mark.parametrize("text", [
    "Order HM-1025 costs ₦499,000 and ships in 3 to 7 days.",
    "The R&D team is not involved.",
    "Your case number is 12; reply within 2 business days.",
])
def test_ordinary_text_is_untouched(text):
    assert hide_rule_codes(text) == text
    assert not shows_rule_code(text)


def test_both_agents_hide_codes_even_when_the_model_writes_them(sessions):
    import asyncio

    from app.graph import TrustedAgent
    from app.graph_baseline import BaselineAgent
    from tests.fakes import ScriptedModel, say

    trusted = TrustedAgent(sessions, model=ScriptedModel(responses=[
        say("qa"), say("Unopened items can be returned within 30 days (R2). See F7 for labels.")]))
    baseline = BaselineAgent(sessions, model=ScriptedModel(responses=[
        say("Refunds over ₦300,000 need human approval under **R8**.")]))
    for agent in (trusted, baseline):
        reply = asyncio.run(agent.respond("question"))
        assert not shows_rule_code(reply), reply
