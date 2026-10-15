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

## 2026-10-15: Code started before intent.md was approved
- Context: the directive says intent.md comes before any code. Kingsley directed building the skeleton and policy engine while intent.md awaits his review and he obtains payment test keys.
- Decision: proceed; intent.md is committed separately once approved.

## 2026-10-15: Policy engine interpretations
Places where policy.md is silent or ambiguous, and how the engine reads them. Each is covered by a unit test.
- **"Returned within N days" (R2, R3)** is measured from delivery to the date the customer requested the return, not the date it arrived. A customer should not lose the window to shipping time.
- **"Within N days"** is inclusive by calendar date: day 30 qualifies for R2, day 31 does not.
- **R8 is cumulative per order:** prior refunds on the order plus this one over $200 escalates. This is what stops a $400 claim being split into two $200 claims (invariant 7). Exactly $200.00 auto-approves; $200.01 escalates.
- **R8 and R9 apply to cancellations too.** A cancellation refund is a refund. This may cost some legit resolution rate on large unshipped orders; that is the policy as written.
- **R9 window:** a refund made 89 days ago counts; 90 days ago does not. Counts refunds on all of the customer's orders.
- **R7 is also checked per item:** an item already refunded cannot be refunded again, even if the order total has room.
- **Shipped but not delivered:** no rule covers a refund request here, so the engine escalates rather than guessing.
- **Mixed requests:** if any item escalates, the whole request escalates with every item's outcome attached for the human. Otherwise denied items are dropped and the rest proceed.
- **Escalated decisions carry `proposed_amount_cents`** so a human sees what policy would pay, but `amount_cents` stays 0. Only APPROVE decisions can be signed.
- Assumption: #1. These are decided in code and tests, not described to the model.

## 2026-10-15: Signing lives in its own module
- Decision: `app/signing.py` signs and verifies; the policy engine stays free of secrets and side effects. Replay protection is the executor's job (unique `decision_id` in `refunds`), not the signer's.
