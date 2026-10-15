# Decisions

Each entry: date, decision, context, and which old assumption (section 4 of the directive) it relates to, if any.

## 2026-10-15: Project timeline anchored to Day 1 = 2026-10-14
- Context: Kingsley started Day 1 on 2026-10-14 (directive drafting). The repo was initialised on 2026-10-15.
- Decision: commits and log entries use their real dates. No backdated commits.

## 2026-10-15: LLM provider is OpenAI
- Decision: `LLM_PROVIDER=openai`. Agent model set by Kingsley ("LUNA"); exact model ID to be confirmed. Judge and attacker models default to the same model, configurable via `JUDGE_MODEL` and `ATTACKER_MODEL`. All model creation stays in `app/llm.py`.

## 2026-10-15: Returns are authorized first, refunded on receipt (R2, R3)
- Context: R2 and R3 say the refund happens "once the return is marked received".
- Decision: for return reason codes, the policy engine returns `ReturnAuthorized`. The refund decision is produced when the return is marked received in `/admin` (acting as the warehouse), using the condition recorded there (opened, tags attached).
- Why: the customer's description of the item's condition is never evidence. If "it's unopened" in chat could avoid the restocking fee, R3 would be beaten by one sentence.
- Assumption: #1 (authority lives in code and data, not in what the model is told).
