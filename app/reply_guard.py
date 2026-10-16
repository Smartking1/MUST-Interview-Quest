"""Deterministic check on customer replies after a decision (architecture invariant 8).

Day 4 finding: on turns where the system authorized a return, escalated or
denied, the model sometimes told the customer more than the system decided:
"since it's unopened you'll get a full refund", "staff can review it as an
exception". Wording in prompts and tool results did not stop it.

This module decides in code whether a reply makes such a promise. The graph
gives the model one rewrite with the violation named; if the rewrite still
fails, the reply is replaced with a template built from the tool results,
which code wrote. The model can make the reply better, never riskier.
"""

from __future__ import annotations

import re

DECISION_MARKERS = ("Return authorized", "Passed to staff", "Not eligible", "Not cancelled automatically",
                    "Cannot cancel", "Cannot change address")

# "no" is deliberately absent: "no restocking fee" is a promise. "no exception(s)" is allowed explicitly.
NEGATIONS = re.compile(r"\b(not|never|cannot|can't|can’t|won't|won’t|isn't|isn’t|doesn't|doesn’t|unable|no exceptions?)\b", re.I)

# (pattern, why it is not allowed) checked per sentence, only on decision turns
PROMISES = [
    (re.compile(r"\bexception", re.I), "offers or implies an exception to policy"),
    (re.compile(r"\bguarantee", re.I), "guarantees an outcome"),
    (re.compile(r"\b(full refund|no restocking fee|without (a|any) (fee|restocking))", re.I),
     "states the refund amount or fee before the system has decided it"),
    (re.compile(r"\b(you([’']ll| will)|you are going to|we([’']ll| will))\b[^.]*\b(refund|reimburs|replac|money back|credit)", re.I),
     "promises a future refund, replacement or credit"),
    (re.compile(r"\b(will|[’']ll)\s+(be\s+)?(issue|process|send|pay|approv)\w*\s+(the|a|your)?\s*(full\s+)?(refund|replacement)", re.I),
     "promises a future refund, replacement or credit"),
    (re.compile(r"\brefund\b[^.]*\b(will|[’']ll)\s+be\s+(issued|processed|paid|sent|approved|made)", re.I),
     "promises a future refund"),
    (re.compile(r"\b(marked|flagged|prioriti[sz]ed)\b[^.]*\b(urgent|priority|expedit)|\b(supervisor|manager|senior (agent|staff))", re.I),
     "claims an action the system did not take (cases are only passed to staff)"),
    (re.compile(r"\bsince (it[’']?s|it is|the item is|they[’']?re)\s+(a\s+\w+\s+item\s+)?(unopened|sealed|unused|new|undamaged|with (the )?tags)", re.I),
     "treats the customer's description of the item as established"),
]


# Patterns about amounts and future refunds pass when the sentence ties the outcome to the system's decision
QUALIFIED = re.compile(r"\b(depending on|depends on|according to|based on|determined|decided|recorded condition)\b", re.I)
QUALIFIABLE = {"states the refund amount or fee before the system has decided it", "promises a future refund",
               "promises a future refund, replacement or credit"}


def sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text) if s.strip()]


def is_decision_turn(tool_results: list[str]) -> bool:
    return any(marker in r for r in tool_results for marker in DECISION_MARKERS)


def violations(reply: str, tool_results: list[str]) -> list[str]:
    """Reasons this reply over-promises, or [] if it is fine. Pure and deterministic."""
    if not is_decision_turn(tool_results):
        return []
    found = []
    for sentence in sentences(reply):
        if NEGATIONS.search(sentence):
            continue
        for pattern, why in PROMISES:
            if pattern.search(sentence) and not (why in QUALIFIABLE and QUALIFIED.search(sentence)):
                found.append(f'"{sentence}" {why}')
                break
    return found


def rewrite_instruction(found: list[str]) -> str:
    return ("Your last reply to the customer said more than the system decided:\n- " + "\n- ".join(found) +
            "\nRewrite the reply. State only what the tool results above say happened and what happens next. "
            "Do not state refund amounts, fees, exceptions or future outcomes that the system has not decided.")


def fallback_reply(tool_results: list[str]) -> str:
    """Built only from tool results, which code wrote."""
    decided = [r for r in tool_results if any(m in r for m in DECISION_MARKERS)]
    body = " ".join(decided[-1:]) if decided else "Your request has been recorded."
    body = re.sub(r"\s*for line items \[[\d, ]*\]", "", body)
    body = re.sub(r"\s*Rules: [^.]*\.", "", body).strip()
    return f"Here is what our system recorded: {body} If you have questions, I can pass them to our staff."
