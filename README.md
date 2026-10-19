# Trusted Support

A customer support AI for an online store that can be trusted with refunds. The AI talks to customers; plain, tested code decides every refund, and only that code can move money.

> Trusted Support resolved 98% of legitimate tickets with no unauthorized refunds. A conventional agent on the same model refunded ₦423,500 that its own rules said needed a human, on an ordinary request with no attack involved, and under attack it told customers rules and promises that do not exist in 88% of conversations.

## The problem

Businesses want AI to resolve support tickets, but the valuable tickets involve money: refunds, cancellations, returns. AI agents are built to be helpful and persuadable, and a refund policy must be neither. In 2024 a tribunal held Air Canada liable for a refund rule its chatbot invented. A dealership's chatbot "agreed" to sell a car for $1. Cursor's support bot invented a login policy and customers cancelled.

An audit for this project of five public support agents and official tutorials (`docs/audit.md`) found the same pattern: where a rule lived in code, attacks failed; where it lived in the prompt or in fragile code around the model, outcomes depended on wording. In one tutorial the model classified complaints correctly 18 times out of 18, and a one-line string check sent every non-refundable complaint down the refund path anyway.

## What was built

A web chat assistant for **Harbor Market**, a fictional Nigerian marketplace (prices in naira), with three capabilities:

| Capability | How it works |
|---|---|
| Questions about policy, shipping, payment | Answers only from `policy/policy.md` and `policy/faq.md`, in plain words, and says it does not know otherwise |
| Order support | Status, cancelling an unshipped order, changing an address before shipping, after checking order number and email |
| Refunds and returns | The AI files a request; a policy engine decides; the decision is signed; only an executor can call the payment gateway; large or unusual cases go to a human |

Plus a staff page (`/admin`) for escalated cases and warehouse receipt of returns, a side-by-side view against a conventional agent, and real refunds through Paystack in test mode.

## Store rules

The store's policy (`policy/policy.md`) has twelve rules. The codes (R1 to R12, and F1 to F8 for the FAQ) are internal, for staff, code and tests: customers are told the rule in plain words, and code removes any code from a reply before it reaches them. Every rule is enforced by the policy engine (`app/policy_engine.py`, pure functions, every boundary unit tested), never by the model's instructions.

| Rule | Policy | What the system does |
|---|---|---|
| R1 Unshipped cancellation | An order not yet shipped can be cancelled for a full refund | Refunds automatically, subject to R7, R8 and R9 |
| R2 Unopened return | Unopened items returned within 30 days of delivery get a full refund once received | Authorizes the return; the refund is paid when staff mark it received and record it unopened |
| R3 Opened return | Opened items returned within 15 days get a refund minus a 15% restocking fee; fashion items with tags attached have no fee | Pays on receipt, from the condition staff record, never from what the customer said |
| R4 Defective item | Within 1 year of delivery, after basic troubleshooting, replace or refund | Always sent to staff, whatever the amount |
| R5 Damaged in delivery | Must be reported within 7 days of delivery | Always sent to staff; photos attached to the case |
| R6 Final sale | Final sale items are not refundable | Denied |
| R7 Amount cap | Total refunds on an order never exceed the amount paid | Checked by the engine and again by the executor against the live database; each item can be refunded once |
| R8 Auto-approval limit | A refund over ₦300,000 needs human approval | Counted per order including earlier refunds, so a split claim still escalates |
| R9 Frequency limit | More than 2 refunds per customer in 90 days needs human approval | Escalated |
| R10 No verbal exceptions | Promises claimed from staff, sellers or earlier chats are not honored without a record | Nothing said in chat is evidence; passed to staff if the customer insists |
| R11 Identity | Order details and actions need the order number and the email on the order | Checked in code, in server-side state, before any order detail or action |
| R12 Address change | Only before the order ships | Changed automatically if unshipped |

**When money moves automatically.** The customer never names an amount: the refund tool has none, and the engine calculates it from the order record. The only refund a chat can trigger immediately is cancelling the customer's own unshipped order of ₦300,000 or less, with fewer than two refunds in the last 90 days. Returns are paid only after the warehouse receives them and records their condition. Everything else is denied or waits for a person in `/admin`, and a person can approve above ₦300,000 but never above the amount paid.

## Trusted Support compared with a conventional agent

Both agents use the same model, see the same store policy, and can do the same things: answer questions, look up orders, cancel, change addresses, start returns and refund. The difference is where decisions are made. The baseline's AI reads the rules in its prompt and decides, and its tools carry out whatever it decides. Trusted Support's AI only asks; plain code decides, and only that code can move money.

| | Conventional agent (baseline) | Trusted Support |
|---|---|---|
| Who decides a refund | The model, following rules written in its prompt | The policy engine: plain, unit-tested code (`app/policy_engine.py`) |
| Refund amount | Chosen by the model: `issue_refund(order_number, amount_kobo, reason)` | Computed from the order record; the model's tool has no amount field: `request_refund(order_number, line_item_ids, reason_code)` |
| Path to the payment gateway | The model's refund tool calls it directly | None for the model. A signed decision goes to the executor, the only code holding the gateway, which checks the signature, single use and the amount cap again |
| Identity (R11) | An instruction to check the email | Server-side state set by `verify_identity`, checked in code by every order tool |
| Limits (R7 to R9) | Instructions the model may or may not follow | Enforced in code; the ₦300,000 limit counts every refund on the order, so split claims still escalate |
| Returns (R2, R3) | Can refund on the customer's word ("it's unopened") | Only authorizes the return; the refund is computed when the warehouse records the condition |
| Claimed promises (R10) | Weighed by the model | Never evidence |
| Photos | Shown to the model | Never shown to the model; staff get the photo and a description that quotes any text in it |
| Replies after a decision | Free text | Checked in code (`app/reply_guard.py`); over-promises get one rewrite, then a template built from what the system recorded |
| Human approval | A free-text escalation | A staff case; approval is signed by a named person and goes through the same executor |
| If the model is fooled | It can pay any amount to anyone | It can only ask; the code refuses |

```
Conventional agent:
customer ─► AI (rules in its prompt) ─► issue_refund(amount the AI chose) ─► payment gateway

Trusted Support:
customer ─► AI ─► request_refund(no amount) ─► policy engine (code decides and computes the amount)
                                                     │
                                       approve / deny / send to a human
                                                     │
                                       signed decision ─► executor ─► payment gateway
                                       (only this code holds the gateway; checks the signature,
                                        single use, and never more than was paid)
```

When the model behaves, both agents usually reach the same answer. They differ when it does not: for the conventional agent a wrong decision is a payment (it refunded ₦423,500 on an ordinary request in about half its runs); for Trusted Support a wrong decision is only a request, and the code turns it down. The conventional agent is only as safe as its model on that conversation; Trusted Support's guarantees do not depend on the model. The conventional agent (`app/graph_baseline.py`) is labelled unsafe and exists only for comparison: it is how most tutorials build support agents, not a deliberately weak one.

## Results

Final runs: both agents on the same model (`gpt-5.6-luna`), every suite three times, 474 conversations (`docs/results.md`, logs in `evals/logs/final/`).

| | Trusted Support | Conventional agent (baseline) |
|---|---|---|
| Legitimate tickets resolved correctly | **98%** (59 of 60) | 80% |
| Unauthorized refunds, legitimate tickets | 0 | **₦423,500**, in 2 of 3 runs of one routine request |
| Unauthorized refunds under attack (177 conversations each) | 0 | 0 |
| Replies free of invented policy, adaptive attacker | **69%** | 12% |
| Replies free of invented policy, legitimate tickets | **97%** | 77% |
| Data leaks | 0 | 0 |

What this shows:
- **The conventional agent broke its own refund limit on an ordinary request.** Asked to cancel a ₦423,500 order, it refunded in full instead of sending it to a human, although the ₦300,000 limit was written in its instructions. No attack was needed.
- **Under attack, both agents kept the money on this model.** The difference was in what they told customers: pressed by an adaptive attacker, the conventional agent stated rules, exceptions and outcomes that do not exist in 88% of conversations.
- **Trusted Support stayed useful:** 98% of legitimate tickets resolved without unnecessary escalation.

## Limitations

- **Zero unauthorized refunds is largely guaranteed by the design.** No tool accepts an amount, and the model has no path to the payment gateway. That number alone proves little; the measures that matter are the legitimate resolution rate (is it still useful?) and the invented policy rate (does it tell customers things the system has not decided?).
- **Invented policy is reduced, not solved.** A deterministic check (`app/reply_guard.py`) catches known phrasings of over-promising and falls back to a template. A new phrasing can pass it. Remaining cases are listed in `docs/failures.md`.
- **The invented policy score comes from an LLM judge.** Its verdicts were hand-checked on every run; disagreements are recorded in `docs/failures.md`.
- **On the model used, the conventional baseline did not give money away under attack.** Its only payout came from a routine request it should have sent to a human. See `docs/results.md`.
- No authentication on `/admin` (a name is required so decisions are attributable). No deployment setup. Fictional data only. Paystack test mode only; the app refuses to start on a live key.
- Paystack refunds are queued and settle asynchronously; the app records them as `accepted`, not settled.

## Run it

Needs Python 3.11 or later and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run pytest                      # 173 tests, no API keys needed
```

Without uv, using pip (slower; same pinned versions):

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt    # includes the project itself and pytest
pytest
```

`requirements.txt` is generated from `uv.lock` (`uv export --format requirements-txt --no-hashes --group dev -o requirements.txt`); regenerate it after changing dependencies rather than editing it by hand. With pip, start the server with `uvicorn app.main:create_app --factory --env-file .env`.

### Chat and admin

```bash
cp .env.example .env               # then set OPENAI_API_KEY and LLM_MODEL (no space after =)
uv run --env-file .env uvicorn app.main:create_app --factory --reload
```

- Chat: http://localhost:8000. "Side by side" shows both agents in two panes, each with its own input so each conversation stays correct; "Send to both" sends one identical opening message to both. "Demo orders" lists the fictional orders and emails.
- Staff admin: http://localhost:8000/admin. Approve or deny escalations, mark returns received, see every payment.
- Test Lab: http://localhost:8000/lab. Pick any of the 65 legitimate and attack cases, run it on either agent or both, and see the conversation next to what actually happened: money paid, returns, escalations, reply-check rewrites, pass or fail. Each run uses a fresh database and the fake gateway.
- The default gateway is a fake that records refunds. For real test-mode refunds set `PAYMENT_GATEWAY=paystack` and `PAYSTACK_SECRET_KEY=sk_test_...`, then run `uv run python -m app.paystack_setup checkout` once and follow its instructions.

### Evals

```bash
uv run inspect eval evals/tasks.py            # both agents, all three suites (needs .env)
uv run inspect eval evals/tasks.py -T epochs=3
uv run inspect view --log-dir evals/logs      # browse the committed logs without any key
```

Committed logs in `evals/logs/` let reviewers see every conversation and score without spending anything.

| Suite | Samples | What it tests |
|---|---|---|
| `legit` | 20 | Real customer requests: policy questions, status, cancellation, address change, returns, defective and damaged items |
| `attacks` | 45 | Scripted attacks: social engineering, false promises, injection in text and in photos, fake tool output, boundary dates, split refunds, identity, cross-capability |
| `adaptive` | 14 | An attacker model with a goal and up to 8 turns, adapting to each reply |

## How it works

```
customer ─► router ─► qa | orders | refunds node (model + only its own tools) ─► reply guard ─► customer
                                         │
                                         ▼
                         tools (identity checked in code, no amounts)
                                         │
                                         ▼
                 policy engine (pure functions, no model) ─► signed decision
                                         │
                                         ▼
                 executor (verifies signature, one use, R7 cap) ─► payment gateway
```

- `app/policy_engine.py`: rules R1 to R12 as pure functions. No model, no database, no clock. Every boundary is unit tested.
- `app/signing.py`, `app/executor.py`: HMAC-signed decisions; the executor claims each decision before calling the gateway, rejects replays, re-checks the amount cap against the live database, and leaves uncertain outcomes pending for a human instead of retrying.
- `app/tools.py`: the model's entire reach. Identity lives in server-side state set only by `verify_identity`.
- `app/reply_guard.py`: code decides whether a reply promises more than the system decided.
- `app/graph_baseline.py`: the conventional agent for comparison, labelled unsafe: same model, policy in its prompt, a refund tool that takes an amount.
- `tests/test_malicious_model.py`: every tool driven adversarially, as a fully compromised model would. Money still follows policy.

## Repository guide

| Path | Contents |
|---|---|
| `intent.md` | What was planned on Day 1 |
| `docs/audit.md`, `audit/` | Audit of five public support agents, with adapters and raw results |
| `docs/results.md` | Every eval run, appended, never overwritten |
| `docs/failures.md` | Every failure found, root cause, fix, and what is still open |
| `docs/decisions.md` | Design decisions and why, including assumptions dropped |
| `docs/ai-usage-log.md` | How AI was used, session by session |
| `writeup.md`, `Final directive.md` | Submission documents |
