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
| Questions about policy, shipping, payment | Answers only from `policy/policy.md` and `policy/faq.md`, cites section IDs, says it does not know otherwise |
| Order support | Status, cancelling an unshipped order, changing an address before shipping, after checking order number and email |
| Refunds and returns | The AI files a request; a policy engine decides; the decision is signed; only an executor can call the payment gateway; large or unusual cases go to a human |

Plus a staff page (`/admin`) for escalated cases and warehouse receipt of returns, a side-by-side view against a conventional agent, and real refunds through Paystack in test mode.

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
uv run pytest                      # 160 tests, no API keys needed
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

- Chat: http://localhost:8000. Use "Side by side" to send one message to both agents. "Demo orders" lists the fictional orders and emails.
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
| `writeup.md`, `directive.md`, `demo-script.md` | Submission documents |
