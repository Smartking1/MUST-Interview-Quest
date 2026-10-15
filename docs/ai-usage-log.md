# AI usage log

## Day 2, 2026-10-15, session 1
- Goal: turn the directive into an implementation plan; set up the repo; draft intent.md; build the project skeleton and policy engine.
- What Kingsley directed: draft an implementation plan from CLAUDE.md; Day 1 started 2026-10-14; LLM provider OpenAI (model "LUNA"); go with the proposed return flow (authorize, then refund on receipt). Then: build the skeleton and policy engine while he gets payment test keys.
- What AI produced: implementation plan (in chat), git init, CLAUDE.md renamed from "CLAUDE (9).md", intent.md draft with sourced incident links, docs/decisions.md entries. pyproject (uv), policy/policy.md, app/models.py, app/db.py, app/policy_engine.py, app/signing.py, 65 unit tests (all boundaries in section 8 and 11). Mutation-checked three boundaries (R8 >, R2 day 30, R9 90 days) to confirm tests fail when the rule is wrong.
- Kept: plan structure, return flow proposal.
- Rejected or changed, and why: (pending Kingsley's review of intent.md)
- Failures hit: first pytest run failed to import `app` (missing pythonpath in pytest config); fixed. Noted that the Cursor incident line in the directive says staff "issued refunds"; sources found only confirm users cancelled before staff corrected the policy, so intent.md states only that.
- Time spent:
