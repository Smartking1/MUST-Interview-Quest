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

## Day 3, 2026-10-16, session 1, from about 05:50
- Goal: backfill this log, then continue development (seed data, eval datasets, scorers).
- What Kingsley directed: said "go on with development", interrupted, then asked for the log to be backfilled where needed, noting it is evidence for a job interview.
- What AI produced: this restructured log. Day 2 times rebuilt from file and git timestamps. Day 1 marked for Kingsley to fill instead of reconstructed.
- Kept: (to update at end of session)
- Rejected or changed, and why: AI did not write Day 1 content, because nothing in the repo or session records what happened that day, and the directive forbids writing anything that did not happen.
- Failures hit: (to update at end of session)
- Time spent: (to update at end of session)
