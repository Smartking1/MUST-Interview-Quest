# AI usage log

One entry per working session, appended at the end of the session. Times are local. Where a time comes from a file timestamp or a git commit rather than a note taken during the session, it says so.

Fields marked **[Kingsley to fill]** cover work done outside the repo that only Kingsley can describe. They are left blank rather than reconstructed.

## Day 1, 2026-10-14
- Goal: choose the problem and write the working directive (CLAUDE.md).
- What Kingsley directed: **[Kingsley to fill]**
- What AI produced: **[Kingsley to fill: which AI tools were used to draft CLAUDE.md, and roughly how many drafts]**
- Kept: **[Kingsley to fill]**
- Rejected or changed, and why: **[Kingsley to fill]**
- Failures hit: **[Kingsley to fill]**
- Time spent: **[Kingsley to fill]**
- Evidence in repo: none from this day. The repo was initialised on Day 2. The directive arrived as a file named `CLAUDE (9).md`, last modified 2026-10-15 09:07.

## Day 2, 2026-10-15, session 1, about 09:07 to 09:45
Times from the CLAUDE.md modification time (09:07) and git commits (09:14 to 09:43).

- Goal: turn the directive into an implementation plan, set up the repo, draft intent.md, then build the project skeleton and policy engine.
- What Kingsley directed:
  - Read CLAUDE.md and draft an implementation plan.
  - Answered the plan's open questions: Day 1 started 2026-10-14; LLM provider is OpenAI, model "LUNA"; use the proposed return flow (authorize the return first, refund when the warehouse marks it received).
  - Said he would get the payment test keys himself.
  - Chose to build the skeleton and policy engine next, ahead of the Day 1 audit.
- What AI produced:
  - Implementation plan (in chat): data model, policy engine interface, signed decisions, session-based identity check, graph structure, baseline design, eval harness, day-by-day tasks, risks, open questions.
  - Repo setup: `git init`, renamed `CLAUDE (9).md` to `CLAUDE.md`, created `docs/decisions.md`, `docs/results.md`, this log, `.gitignore`.
  - intent.md draft, with incident links checked by web search.
  - `pyproject.toml` (uv), `policy/policy.md`, `app/models.py`, `app/db.py`, `app/policy_engine.py`, `app/signing.py`.
  - 65 unit tests: every rule R1 to R12, every window boundary (day 7/8, 15/16, 30/31, 365/366, $200.00/$200.01, refunds 89/90 days ago), cumulative caps, a $400 claim split into two $200 refunds, double refunds of the same item, forged, altered and expired signed decisions.
  - Nine policy interpretations recorded in `docs/decisions.md` where policy.md is silent or ambiguous.
- Kept: plan structure; return flow (decision recorded); policy engine and tests as written, pending Kingsley's review of the interpretations.
- Rejected or changed, and why:
  - The directive's Day 1 order (intent approved, then audit, then code) was changed by Kingsley: code started while intent.md waits for his review. Recorded in `docs/decisions.md`.
  - AI changed one claim from the directive: CLAUDE.md says Cursor staff "issued refunds". The sources found only confirm users cancelled before the co-founder corrected the invented policy, so intent.md states only that.
  - AI left the Air Canada damages figure out of intent.md: sources disagree (CA$650.88 damages vs about CA$812 total with interest and fees). The figure should be checked against the decision text before it is used.
  - AI removed an unused helper function from the policy engine before committing.
- Failures hit:
  - The first test run failed: pytest could not import `app` because `pythonpath` was missing from the pytest config. Fixed in `pyproject.toml`.
  - AI ran `git add -A` before a commit and staged intent.md by mistake (it had not been approved). The commit used explicit paths, so intent.md was not committed; AI unstaged it straight away.
  - Tests passed on the first run, which on its own proves little. AI deliberately broke three boundaries (R8 `>` changed to `>=`, R2 window widened to 31 days, R9 window widened to 90 days). The tests caught each one (2, 2 and 1 failures), and the original code was restored.
- Time spent: about 40 minutes (from timestamps). **[Kingsley to confirm, and add any time spent outside the session]**

## Day 3, 2026-10-16, session 1, from about 05:50 WAT
- Goal: backfill this log, then continue development: seed data, eval harness, then the Day 2 core system (tools, graph, baseline).
- What Kingsley directed: said "go on with development", interrupted to ask for the log to be backfilled (evidence for a job interview), then said to keep developing and keep the log updated, with discrepancies to be settled later.
- What AI produced:
  - Log restructure: Day 2 times rebuilt from file and git timestamps; Day 1 marked for Kingsley to fill instead of reconstructed.
  - `app/seed.py`: 25 orders for 10 fictional customers, each pinned to a rule or boundary. `app/clock.py`, `app/repository.py`.
  - `app/gateway.py` (FakeGateway with ledger), `app/executor.py` (signed decisions only, replay check, live R7 re-check, rollback on gateway failure).
  - Eval harness: `evals/datasets/legit.jsonl` (20), `evals/datasets/attacks.jsonl` (22), `evals/scorers.py`, `evals/user_sim.py`, `evals/tasks.py`. Stub agent run committed to `evals/logs/` and `docs/results.md`.
  - `policy/faq.md`, `app/llm.py`, `app/retrieval.py`, `app/tools.py`, `app/graph.py` (router plus three nodes), `app/graph_baseline.py` (labelled unsafe).
  - Tests grew from 65 to 117, including the malicious model test and scripted-model graph tests. All keyless.
  - Day 3 product surface (ahead of keys): `app/main.py` (FastAPI), `app/admin.py` (approve and deny escalations, warehouse receipt of returns), `app/escalations.py`, `app/static/index.html` (Trusted, Baseline, Side by side), `app/static/admin.html` (escalation queue, returns, payment ledger), `.env.example`. 123 tests. Server smoke-tested: pages load, admin endpoints work, chat returns a clear 503 until a model is configured.
- Kept: all of the above.
- Rejected or changed, and why:
  - AI did not write Day 1 content: nothing in the repo or session records it, and the directive forbids writing anything that did not happen.
  - AI dropped a draft heuristic that tagged escalations as R10 when the word "promise" appeared: string matching on model text is exactly the kind of fragile check this project argues against.
  - AI considered embeddings for retrieval and chose lexical search plus a table of contents (decision recorded).
- Failures hit:
  - The executor replay test first passed for the wrong reason: the replayed full refund was blocked by the R7 cap, not the replay check. A replayed partial refund would have been caught only by the database unique constraint. Added an explicit replay check that runs first, and changed the test to a partial refund.
  - `inspect eval` could not import `app`. Fixed by making the project an installable package.
  - The malicious model test missed a deliberately broken policy engine (see decisions.md, 2026-10-16). Strengthened; it now catches it.
  - Tests are mutation-checked: R8, R2 and R9 boundaries, removing the identity check (4 failures), and turning policy denials into payouts (caught after the fix).
  - Audit, code review half (started 06:12): pinned five targets in `audit/targets.md` and wrote code review findings in `docs/audit.md`. Confirmed the directive's discovery claim at the pinned commit (T1 `nodes.py:66`). Found two further T1 issues by reading the code, and noted strengths fairly (T2 identity, T4 and T5 amounts from the database).
- Not yet done: no run against a real model. Waiting for the OpenAI key and the exact model ID for "LUNA".
- Time spent: about 30 minutes of session time, 05:50 to about 06:20 WAT (from git commit times). **[Kingsley to confirm]**

## Day 3, 2026-10-16, session 2
- Goal: continue Day 3: real payment gateway in test mode, image upload, one real test-mode refund.
- What Kingsley directed: "go on with day 3".
- What AI produced:
  - `StripeGateway` in `app/gateway.py` (test mode only, refuses live keys, idempotency key = decision_id), `app/stripe_setup.py` (test PaymentIntents for seeded orders), `stripe` dependency (in the directive's stack).
  - Photo upload: `app/attachments.py`, `Attachment` model, photo handling in both agents, `/api/admin/attachments/{id}`, photo picker in the chat page, thumbnails in the admin escalation queue.
  - Tests: live key refusal, idempotency key passed to Stripe, the Trusted model never receiving photo content (checked against everything the model was given), photos linked to escalations, and the baseline model receiving the photo. 136 tests, keyless.
- Kept: all of the above.
- Rejected or changed, and why: showing photos to the Trusted model with a "do not follow instructions in images" prompt was rejected in favour of not showing them at all (decisions.md).
- Failures hit: Docker Desktop did not start within two minutes, so `stripe-mock` could not be run. The Stripe gateway is unit-tested against a recording stand-in instead; the real check waits for test keys.
- Not yet done: one real test-mode refund end to end (needs Stripe test keys); any run against a real model (needs the OpenAI key and model ID).
- Time spent: session ended about 06:24 WAT (time from the system clock; start time not recorded). **[Kingsley to confirm]**

## Day 3, 2026-10-16, session 3
- Goal: switch the payment gateway to Paystack.
- What Kingsley directed: switch to Paystack, because he cannot create a Stripe account in Nigeria.
- What AI produced:
  - Research: Paystack's docs site returned 403 to automated fetches, so AI read Paystack's official OpenAPI spec from GitHub instead. Found that refunds take no idempotency key and the charge API takes no raw card details.
  - Two-phase executor (claim, call, finish), `Refund.status`, and limits that count pending refunds.
  - `PaystackGateway` (httpx, test keys only), `app/paystack_setup.py` (one checkout, then reusable authorization for the rest), `app/payment_refs.py` (references survive demo resets). Removed the Stripe gateway, its tests and the `stripe` dependency; added `httpx` as an explicit dependency (it was already installed through other packages).
  - Tests: request shape sent to Paystack, 4xx versus 5xx handling, crash after paying, timeout, live key refusal, references surviving a reset. 141 tests, keyless.
- Kept: all of the above.
- Rejected or changed, and why: AI first planned to mark any gateway exception as `failed`. Changed before committing: a timeout may have paid, so only a definite rejection marks a refund failed (decisions.md).
- Failures hit: `paystack.com/docs` returned 403 to both the fetch tool and curl; worked around with the official spec on GitHub. One existing executor test encoded the old behaviour (roll back and retry the same decision) and failed as expected; rewritten for the new behaviour.
- Not yet done: the real test-mode payment and refund need Kingsley's Paystack test secret key and one checkout payment with a test card.
- Time spent: (to update at end of session)
