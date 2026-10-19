"""Rule codes are internal: customers never see them (Kingsley's requirement, 2026-10-19).

Policy sections are labelled R1 to R12 and F1 to F8 for staff, code and
evals. Customers get the rule in plain words. Both agents are told this in
their instructions, and this module enforces it in code on every reply
before it leaves the server. Staff case summaries keep the codes.
"""

from __future__ import annotations

import re

_CODE = r"(?:\*\*)?\b(?:R(?:1[0-2]|[1-9])|F[1-8])\b(?:\*\*)?"
_LIST = rf"{_CODE}(?:\s*(?:,|and|/|&)\s*{_CODE})*"

_STEPS = [
    (re.compile(rf"\s*(?:\*\*)?\(\s*{_LIST}\s*\)(?:\*\*)?"), ""),                       # "(R2, R3)", "**(R2)**"
    (re.compile(rf"\s*\bRules?:\s*{_LIST}\.?", re.I), ""),                             # "Rules: R1, R8."
    (re.compile(rf"\b(?:our\s+)?(?:policy|rule|section)\s+{_LIST}", re.I), "our policy"),  # "policy R12"
    (re.compile(rf"\b(under|per|following|according to|see|in)\s+{_LIST}", re.I), r"\1 our policy"),
    (re.compile(_LIST), "our policy"),                                                  # anything left
]

_DETECT = re.compile(r"\b(?:R(?:1[0-2]|[1-9])|F[1-8])\b")


def hide_rule_codes(text: str) -> str:
    for pattern, replacement in _STEPS:
        text = pattern.sub(replacement, text)
    text = re.sub(r"[ \t]+([.,;:!?])", r"\1", text)   # no space before punctuation
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\(\s*\)", "", text)
    return text.strip()


def shows_rule_code(text: str) -> bool:
    return bool(_DETECT.search(text))
