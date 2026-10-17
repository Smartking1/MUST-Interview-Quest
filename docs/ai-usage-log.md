# AI usage log

One entry per working session, appended at the end of the session. Times are local. Where a time comes from a file timestamp or a git commit rather than a note taken during the session, it says so.

Fields marked **[Kingsley to fill]** cover work done outside the repo that only Kingsley can describe. They are left blank rather than reconstructed.

## How this log is organised

The log follows the five phases of the plan in `directive.md`. Each entry keeps the date and time it actually happened. The work was compressed: phases 3, 4 and part of 5 all ran on 2026-10-16, and the git history shows the same dates.

| Plan day | Phase | When it happened |
|---|---|---|
| Day 1 | Problem, solution and directive | 2026-10-14 |
| Day 2 | Repository, policy engine, tests | 2026-10-15 |
| Day 3 | Core system, product, payments, first real evals, audit | 2026-10-16, about 05:50 to 16:23 WAT |
| Day 4 | Stress: adaptive attacker, harder attacks, fixes | 2026-10-16, from about 16:24 WAT |
| Day 5 | Final runs, documents, demo, submission | 2026-10-16 onward, until submission on 2026-10-19 |

# Day 1: problem, solution and directive

### 2026-10-14
- Goal: choose the problem and write the working directive (CLAUDE.md).
- What Kingsley directed: worked out the problem and the solution with Claude (web version), producing CLAUDE.md.
- What AI produced: drafts of CLAUDE.md in Claude (web version). Source: Kingsley, recorded on 2026-10-16.
- Kept: CLAUDE.md, the file this repository was built from.
- Rejected or changed, and why: not recorded.
- Failures hit: not recorded.
- Time spent: about 5 hours (Kingsley's estimate).
- Evidence in repo: none from this day. The repo was initialised on Day 2. The directive arrived as a file named `CLAUDE (9).md`, last modified 2026-10-15 09:07.

# Day 2: repository, policy engine, tests

### 2026-10-15, about 09:07 to 09:45
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

# Day 3: core system, product, payments, first real evals, audit

### 2026-10-16, session 1, from about 05:50 WAT
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

### 2026-10-16, session 2
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

### 2026-10-16, session 3
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
- Time spent: session ended about 08:31 WAT (system clock; start not recorded). **[Kingsley to confirm]**

### 2026-10-16, session 4
- Goal: switch the store currency to naira.
- What Kingsley directed: "switch the currency to naira" (choosing this over AI's recommendation to keep USD and send cents one to one as kobo).
- What AI produced: renamed every `_cents` field to `_kobo` across code, tests and datasets; repriced the seed catalogue in naira; R8 limit ₦300,000; naira formatting in summaries and UI; policy and FAQ text; `naira_given_away` scorer; CLAUDE.md updated; Paystack gateway and setup docstrings simplified now that no conversion note is needed.
- Kept: all of the above. The ₦300,000 limit is AI's choice, flagged for Kingsley to confirm.
- Rejected or changed, and why: AI's earlier recommendation (keep USD, send one to one) was overruled by Kingsley.
- Failures hit: the first bulk rename did nothing because zsh does not split an unquoted variable into separate file arguments; rerun through xargs. 15 tests failed after repricing, all on hard-coded dollar-era amounts, as expected; updated, with R8 tests tied to the limit constant. One test kept passing for a meaningless reason after repricing and was rewritten. R8 off-by-one mutation re-checked: caught (3 failures).
- Time spent: session ended about 08:55 WAT (system clock; start not recorded). **[Kingsley to confirm]**

### 2026-10-16, session 5, until about 13:40 WAT
- Goal: use the keys Kingsley provided: first real eval runs, Paystack test payment.
- What Kingsley directed: provided the OpenAI key, model (`openai/gpt-5.6-luna`) and Paystack test key.
- What AI produced:
  - Found the keys had been entered in `.env.example` (tracked by git) before any commit; moved them to `.env` (ignored), restored the template, confirmed nothing in git history. Filled judge and attacker model and a random decision secret in `.env`.
  - Verified both keys with harmless calls. Created the Paystack test checkout for HM-1001.
  - Smoke test (3 samples), then the first full run: both agents on both datasets (84 samples). Results in `docs/results.md`; failures and judge hand-checks in `docs/failures.md` (new file).
  - Harness fixes found by the smoke test: judge now sees tool results; `outcome_match` fails unnecessary escalations; FAQ F7 (return label) added; LLM factory moved to the Responses API.
- Kept: all fixes. The scorer change makes the eval stricter.
- Rejected or changed, and why: AI considered iterating on the return wording until the invented policy flags went away. Stopped after one change: the remaining failure is the model promising on the customer's word, a wording fix is a prompt-level mitigation, and the directive says to fix with architecture. Logged as open for Day 4.
- Failures hit: Chat Completions rejected tool calls for this model (fixed). Inspect refused `--limit` with `--sample-id` (dropped `--limit`). Judge false positive from missing tool results (fixed). Unnecessary escalation passed the old scorer (fixed). The baseline gave away nothing on scripted attacks: the Day 2 attack suite does not separate the agents.
- Not yet done: the Paystack checkout shows "abandoned" (not paid yet); the real refund waits on that payment. Runtime half of the audit now unblocked.
- Time spent: **[Kingsley to confirm]** (end time from the system clock)

### 2026-10-16, session 6, until about 16:21 WAT
- Goal: runtime half of the audit.
- What Kingsley directed: "go on" (start the audit runtime while he completes the Paystack payment).
- What AI produced:
  - Core attack set (8 conversations, `audit/harness/README.md`) and adapters for T1, T3, T4, T5 that call each target's own entry point with no change to target code. `audit/harness/with_env.py` loads `.env` without printing values.
  - Runs: T1 classifier node (18 calls), T3 on current packages and on packages as of its commit date, T4 (does not run), T5 from its lockfile with SendGrid blocked by a dead local proxy. Results in `audit/results/`, write-up in `docs/audit.md`.
  - Headline: T1's model answered correctly 18 of 18 times and its code routed all 12 non-refundable complaints to the refund path. T3 issued vouchers on a claimed staff promise in both preserved runs and cancelled a third party's flight. T5's code-enforced threshold held.
- Kept: all results, with counts restricted to preserved runs.
- Rejected or changed, and why:
  - T2 not run: it needs Anthropic and Tavily keys; swapping its model and removing its search tool would test a different program.
  - T4: tried three LangGraph versions and its commit-date packages before stopping, rather than patching its code.
  - AI's first T1 harness draft had dead code from working out how to capture raw outputs; rewritten before committing.
- Failures hit:
  - **AI exposed Kingsley's OpenAI key and Paystack test key in this session's output** by loading `.env` with shell `source`: lines with a space after `=` were run as commands and the shell echoed the values in errors. The keys did not reach git or any file. Kingsley asked to rotate both. Replaced with a parser (`with_env.py`).
  - AI overwrote two results files by re-running into the same path (T3's first run, T5's first run). The audit cites only preserved runs; an earlier "3 of 3" claim for T3 was corrected to "2 of 2".
  - T5 attack A6 was first worded so the agent asked for an order ID instead of refunding, so it did not test a double refund; reworded and re-run.
  - `with_env.py` first looked for `.env` in the current directory, so a run from a target's folder had no key; fixed to use the project root.
- Paystack HM-1001 checkout was paid by Kingsley during the session; see session 7.
- Time spent: audit runtime from about 15:50 to 16:21 WAT (file times). **[Kingsley to confirm]**

### 2026-10-16, session 7, until about 16:23 WAT
- Goal: complete Day 3: real test-mode payments and one real refund through the chat.
- What Kingsley directed: paid the HM-1001 test checkout with a Paystack test card.
- What AI produced: ran `app.paystack_setup finish` (23 of 25 orders paid; HM-1019 and HM-1020 failed with "Insufficient Balance"); started the real server with the Paystack gateway and cancelled HM-1001 through the chat API; verified the refund at Paystack and in our database (`docs/results.md`).
- Kept: the end-to-end refund evidence.
- Rejected or changed, and why: renamed refund status `succeeded` to `accepted`, because Paystack showed the refund as queued; "succeeded" overstated what we knew.
- Failures hit: AI's setup script saved payment references for the two failed charges; caught from the script's own output, references removed, script fixed to save only successful payments.
- Time spent: **[Kingsley to confirm]**

# Day 4: stress

### 2026-10-16, session 8, about 16:24 to 16:49 WAT
- Note: Kingsley asked to start Day 4 work at 16:24 on 2026-10-16. Dated as it happened.
- Goal: stress: adaptive attacker, about 45 attacks including cross-capability and image injection, fix failures with architecture.
- What Kingsley directed: "go on with day 4".
- What AI produced: `evals/attacker.py` (adaptive attacker through Inspect), `adaptive` task and 14 goals, 23 new scripted attacks (45 total) including two image-injection photos generated once with a temporary Pillow, `forbidden_effects` in outcome scoring. Suite committed before any run. Fixes: duplicate returns refused in the policy engine; `app/reply_guard.py` (three iterations, each test-first); FAQ F8; leak scorer ordering. Supplementary `gpt-4o-mini` runs. Results, failures and decisions written up.
- Kept: all fixes; every guard change has a test that failed first.
- Rejected or changed, and why:
  - Stopped tuning the guard after three iterations: remaining invented-policy flags are varied one-offs, and further patterns would fit this judge rather than improve the agent.
  - AI first described the baseline's adv-06 failure as "cancelled a shipped order"; checking the observed effects showed it authorized a return on an undelivered order. Corrected before writing it down.
  - Did not change the headline claim: the evidence no longer supports "under attack"; flagged to Kingsley as his decision (decisions.md).
- Failures hit: ten in the fixes and harness, listed in `docs/failures.md` (Day 4 section), including a vacuous test assertion (`... or True`) that AI wrote and then removed, and a guard template that caused an unnecessary escalation.
- Time spent: about 16:24 to 16:49 WAT (system clock). **[Kingsley to confirm]**

### 2026-10-16, session 10, about 17:57 to 18:07 WAT (the Saturday work list, done on the 16th)
- Goal: the stress work planned for Saturday: fix the router misroute, fix an over-strict eval check, a stronger attacker, re-run.
- What Kingsley directed: "keep going for saturday work", and to modify the logs to match the five days when done. AI declined to change dates or relabel work as done on days it was not, because the log and git history are evidence for the interview; instead the log was organised by the plan's five phases with true dates (session 9 entry above and the table at the top).
- What AI produced: router fix (`request_refund` in the orders node, test first); atk-15 check accepts any clear denial (recorded in failures.md); eight new adaptive goals (22 total) aimed at small "reasonable" payouts and at the guard's known gaps, committed before running; full re-run; log reorganised by phase.
- Kept: all of the above.
- Rejected or changed, and why: see "What Kingsley directed".
- Failures hit: the re-run's adaptive tasks failed on OpenAI rate limits and then exhausted credits; only legit and attacks completed (results.md). AI ran all six tasks concurrently, which contributed to hitting the rate limit.
- Time spent: about 17:57 to 18:07 WAT (system clock).

# Day 5: final runs, documents, demo, submission

### 2026-10-16, session 9, until about 17:25 WAT
- Note: Kingsley asked to keep building; the remaining items are Day 5 deliverables. Dated as it happened.
- Goal: close the definition of done and draft the submission documents.
- What Kingsley directed: "lets keep building, what is left?"
- What AI produced:
  - Six explicit eval tasks so `uv run inspect eval evals/tasks.py` runs both agents on every suite with no flags (verified; Inspect reads `.env` itself).
  - Real check of photo descriptions for staff: the fake receipt was described as a receipt, not the vase, and its injected instruction quoted as text.
  - Final runs: six tasks, three epochs, 474 conversations, 0 errors (`docs/results.md`), with hand-checks (`docs/failures.md`).
  - Drafts: `README.md` (results table filled, headline pending), `directive.md` (CLAUDE.md as it produced the system, three invariants added, how it evolved), `demo-script.md` (every shot tested on the real server with Paystack).
  - App: the baseline gets its own database (side by side runs had shared one); Paystack `recharge` command for demo takes.
- Kept: all of the above.
- Rejected or changed, and why:
  - A planned demo shot (the baseline authorizing a duplicate return) was dropped: the live test showed the "duplicate" was the seeded return, and the baseline only asked a question. Showing it would have misled.
  - HM-1004 replaced by HM-1001 for the legitimate refund shot: its customer has two recent refunds, so R9 correctly sends it to a human.
  - `directive.md` does not repeat CLAUDE.md's unverified claim that Cursor staff issued refunds.
- Failures hit:
  - Side by side mode shared one database between both agents, so one agent's actions changed what the other saw. Fixed (separate baseline database, test added).
  - A refunded Paystack test payment cannot be refunded again, so demo tests consumed the payments; added `recharge`.
  - One of AI's eval checks was too strict: atk-15 required the reply to contain "30", and the baseline's correct "No, there is no 60 day window" failed it. Not changed, since the final run was frozen; recorded here.
  - Shot 1 is not reproducible on demand: the baseline refunded the over-limit cancellation in 2 of 3 eval runs but escalated in the live test. The script says so and gives a fallback.
- Also drafted `writeup.md` (895 words, first person, headline per AI's recommendation pending Kingsley's choice); first draft was 949 words and was trimmed to the 900 limit.
- Flagged to Kingsley: the git history shows only 2026-10-15 and 2026-10-16, because Days 3 to 5 of the plan ran on one calendar day. No dates were altered.
- Not yet done: headline wording (Kingsley), `intent.md` approval, Day 1 log entry, usage log completeness check.
- Time spent: **[Kingsley to confirm]**

### 2026-10-18, session 11, about 00:38 to 00:39 WAT
- Goal: Day 5 housekeeping.
- What Kingsley directed: approved `intent.md`; set the commit author email to ibekwekingsley2000@gmail.com; asked what the "headline choice" means.
- What AI produced: committed `intent.md` unchanged (approved 2026-10-18; it had been drafted 2026-10-15 and held until approval, later than the directive's Day 1); rewrote the author and committer email on all 45 commits (the repository had never been pushed; dates and contents unchanged; backup branch `backup-before-email-rewrite` kept); set the repository's `user.email`.
- Failures hit: a read-only check after the rewrite was blocked by the permission system; the rewrite's own output had already shown no content changes and the original dates.
- Time spent: a few minutes.

### 2026-10-18, session 12, until about 00:45 WAT
- Goal: apply the headline; build a simple frontend for testing.
- What Kingsley directed: chose the recommended headline; asked for a simple testing frontend.
- What AI produced: headline in README.md, writeup.md and directive.md (decision recorded); Test Lab at `/lab` (`app/lab.py`, `app/static/lab.html`): pick any of the 65 legit and attack cases, run on either agent or both, see the transcript beside the database effects and the programmatic verdict; each run isolated in a fresh database with the fake gateway. Links from the chat and admin pages; three API tests.
- Kept: all of the above.
- Rejected or changed, and why: a live UI click-through was not possible from this environment; the page was checked by JavaScript syntax check, served-page and API tests, and one real run attempt.
- Failures hit:
  - Testing the lab showed that the README and demo script told people to start the server with plain `uvicorn`, which does not read `.env`, so the app came up with no model. Fixed to `uv run --env-file .env uvicorn ...` in README.md, demo-script.md and app/main.py.
  - The OpenAI account is out of credits; a real lab run returned a bare 500. Model provider errors now return a clear 503 message in the lab and the chat (test added).
- Time spent: (system clock end time above)
