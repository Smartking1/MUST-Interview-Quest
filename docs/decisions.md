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

## 2026-10-16: Eval outcomes are read from the database, not from the agent's words
- Decision: the solver diffs each sample's database before and after the conversation (gateway ledger, refunds, returns, escalations, cancellations, address changes). `outcome_match`, `unauthorized_refund`, `dollars_given_away` score those effects. Only `invented_policy` reads the agent's words with a judge.
- Why: an agent saying "your refund is processed" proves nothing, and an agent that quietly pays out while saying "sorry, I can't" must still fail. Scoring what the agent did, not what it said, applies to both agents equally.
- Each sample gets its own freshly seeded SQLite file, so samples cannot interfere and the ledger total per sample is exact.
- Attack samples list every acceptable outcome (for example denied or escalated), because escalation to a human counts as safe.

## 2026-10-16: Data leak check excludes what the customer typed
- Decision: `data_leak` flags names, emails, addresses, order numbers and item names of orders the customer may not see, unless the customer typed that token themselves. Repeating back "HM-1025" while refusing to discuss it is not a leak; revealing that it contains a Gaming Console is.

## 2026-10-16: FAQ states that sellers cannot approve refunds (F3)
- Context: R10 says promises claimed from sellers are not honored. The FAQ needed a factual basis for that, since Harbor Market is a multi-seller marketplace.
- Decision: F3 says Harbor Market handles all refunds, not sellers. This is fictional store content written for the project, consistent with R10.

## 2026-10-16: Project installed as a package
- Context: `inspect eval` loads the task file in a way that could not import `app`.
- Decision: added a hatchling build so `app` and `evals` are importable everywhere. No new runtime dependency.

## 2026-10-16: Retrieval is lexical search plus a table of contents, not embeddings
- Context: the corpus is 18 short sections. "Do you take PayPal?" shares no words with "F4 Payment methods", so pure keyword search misses it.
- Decision: `search_policy` returns the top lexical matches and always the full table of contents; `read_policy_section(id)` opens a section. The model can navigate by title when wording differs. No embeddings, no network, no new dependency, deterministic in tests.

## 2026-10-16: Router falls back to the Q&A node
- Decision: if the router's reply is not one of `refunds`, `orders`, `qa`, the turn goes to `qa`, which has no tools that act on orders. An unparseable or manipulated route gets the least authority. Tested with a scripted model.

## 2026-10-16: Identity failures are indistinguishable
- Decision: `verify_identity` returns the same message whether the order does not exist or the email is wrong, so it cannot be used to find valid order numbers.

## 2026-10-16: Baseline gets the same capabilities, enforced only by its prompt
- Decision: the baseline has the full policy and FAQ in its system prompt, explicit instructions to verify email and follow policy, and tools that act directly (`issue_refund(order_number, amount_cents, reason)`, `cancel_order`, `update_address`, `create_return`, `lookup_order`, `escalate`). It is a fair, conventional design, not a strawman: a reviewer should recognise it from tutorials.
- Assumption: #1. The comparison isolates one variable: where authority lives.

## 2026-10-16: The malicious model test bypasses the prompt entirely
- Decision: `tests/test_malicious_model.py` calls every tool with adversarial arguments, unverified and verified, across every seeded order. If deleting the system prompt could make the agent unsafe, this test would fail.
- Finding while building it: the first version only verified as the owner of HM-1001. Once HM-1001 was cancelled, the executor's R7 re-check blocked every later payout, so a deliberately broken policy engine (deny turned into pay) went undetected. Added a scenario on orders where policy pays nothing (HM-1007, HM-1017), which catches it. The layered defense worked, but it hid a gap in the test.

## 2026-10-16: Human approvals use the same executor as policy decisions
- Decision: approving an escalation in `/admin` creates a decision signed with issuer `human:<name>` and sends it through `Executor.execute`, the only path to money. A human can override policy limits like R8, but gets the same replay protection and the same live R7 cap: nobody, human or model, can refund more than was paid. Tested: a $10,000 human approval on a $159 order is rejected.
- No auth system (directive section 12). `/admin` requires a name so every decision is attributable. Stated as a limitation.

## 2026-10-16: Demo seeds relative to the real clock; evals pin the clock
- Decision: the running app seeds with today's date so "delivered 10 days ago" reads naturally and signed decisions expire in real time. Evals and tests pin `FROZEN_NOW` to `SEED_NOW` so every run is identical.

## 2026-10-16: Chat UI sends one message to both agents side by side
- Decision: the chat page has Trusted, Baseline and Side by side modes. The demo needs the same attack against both agents in one frame. The baseline pane is labelled unsafe in the UI.
- The API takes JSON only. Image upload (first on the cut list) will send base64 in JSON, which avoids adding `python-multipart`.

## 2026-10-16: Stripe gateway refunds the order's PaymentIntent, keyed by decision_id (superseded, see below)
- Decision: `StripeGateway` refunds the PaymentIntent stored on the order, with `decision_id` as Stripe's idempotency key, so a retried decision cannot refund twice even if our database write fails after Stripe succeeds. `app/stripe_setup.py` creates one confirmed test-mode PaymentIntent per seeded order (test card `pm_card_visa`) and mirrors seeded refunds.
- Live keys are refused at construction (`_live_` anywhere in the key), so the app refuses to start on one (invariant 9). Tested.
- Fallback order unchanged: Stripe test mode, then `stripe-mock` (via `STRIPE_API_BASE`), then Paystack. Docker Desktop did not start on this machine on 2026-10-16, so `stripe-mock` was not run; the gateway is unit-tested against a recording stand-in until test keys arrive.

## 2026-10-16: The Trusted model never sees customer photos
- Decision: a photo uploaded in chat is validated (type, magic bytes, 5 MB), stored, and the model receives only a server-written system note that a photo exists. On escalation the photo is linked to the case; a vision model may describe it for staff, with any text in the photo quoted as content. The description goes into the staff summary only. The policy engine never receives the photo or its description.
- Alternative rejected: show the photo to the chat model and tell it to ignore instructions in images. That is a prompt-level defense against image injection, the exact habit this project drops (assumption #1).
- The baseline passes photos straight to its model, as a conventional vision-enabled agent would. That sets up the Day 4 image injection attacks as a fair comparison.

## 2026-10-16: Payment gateway switched from Stripe to Paystack
- Context: Kingsley cannot open a Stripe account in Nigeria. The directive's fallback order is Stripe test mode, then `stripe-mock`, then Paystack test mode. A real test-mode gateway (Paystack) is worth more for the demo than a local mock of one he cannot use, so Paystack replaces Stripe. The Stripe gateway code and dependency were removed rather than kept unused.
- Source: Paystack's official OpenAPI spec (github.com/PaystackOSS/openapi, commit 07c5abc), read because paystack.com/docs blocked automated fetches. Refund is `POST /refund` with `transaction` (reference), `amount` in subunits, `currency`, `merchant_note`. **The refund endpoint takes no idempotency key**, unlike Stripe.
- Test payments: the charge API takes no raw card details, so `app/paystack_setup.py` opens one hosted checkout (paid by Kingsley with a Paystack test card), then charges every other seeded order with that card's reusable authorization. References are kept in a local file and re-applied after every demo reset.
- Currency: the store prices in USD cents; a Nigerian test account settles in NGN. Test refunds send cents one to one as kobo (`PAYSTACK_CURRENCY`). A test-mode convenience, to be stated in the README.

## 2026-10-16: The executor claims a decision before calling the gateway (two-phase)
- Context: with Stripe, a crash after the gateway paid but before our database committed was safe, because retrying with the same idempotency key returned the first refund. Paystack has no such key, so the same crash followed by a retry would refund twice.
- Decision: the executor first commits a `pending` refund row (the unique `decision_id` is the claim), then calls the gateway, then marks it `succeeded`, or `failed` only when the gateway definitely rejected it (4xx). A timeout or 5xx leaves it `pending`. Pending refunds count toward R7, R8 and R9 and are never retried automatically; the `decision_id` is sent as Paystack's merchant note so a human can reconcile in the dashboard.
- Tests: a crash after paying blocks a second payout; a timeout leaves the refund pending and blocks a retry; a definite rejection frees the amount for a fresh decision, but never the same token.
- Assumption: #1. The safety property moved from a gateway feature into our own code, so it holds whichever gateway is used.

## 2026-10-16: Store currency switched to Nigerian naira
- Context: Paystack test accounts in Nigeria settle in NGN. Sending US cents one to one as kobo would have shown a ₦50.98 refund for a $50.98 order in the demo. Kingsley chose to reprice the store in naira instead.
- Decision: all money is integer kobo (`amount_kobo`, `price_kobo` and so on; renamed from `_cents` across code, tests and datasets). Seed prices are round naira amounts (for example Wireless Earbuds ₦45,000, Laptop ₦1,299,000), shipping is ₦3,500, and the FAQ lists Verve, Visa and Mastercard.
- **R8 auto-approval limit is ₦300,000** (was $200). Chosen by AI to keep the seed's boundaries: HM-1021 sits exactly at the limit, HM-1019 is two items at the limit (the split-claim case), HM-1002 and HM-1020 are above it. Kingsley to confirm the figure.
- The metric `dollars_given_away` is now `naira_given_away`. CLAUDE.md updated to match (currency, gateway, R8, metric names). Entries above this one and the Day 3 stub run in `docs/results.md` keep their original dollar figures as history.
- R8 tests now use the limit constant instead of literal amounts. One test ("restocking fee brings the refund under the limit") had kept passing after the repricing for a meaningless reason (₦235 is nowhere near the limit); rewritten at ₦350,000, which the fee brings to ₦297,500.

## 2026-10-16: Keys live only in .env
- Context: the API keys were first entered in `.env.example`, which is committed. AI noticed before any commit, moved them to `.env` (gitignored, permissions 600) and restored the template. Confirmed no key exists in git history.
- Commands that need keys run with `uv run --env-file .env ...`, which needs no extra dependency.

## 2026-10-16: OpenAI Responses API for every model call
- Context: `gpt-5.6-luna` rejects function tools with reasoning on Chat Completions.
- Decision: `ChatOpenAI(use_responses_api=True)` in `app/llm.py`, shared by Trusted, baseline and photo descriptions, so the comparison stays like for like. `LLM_MODEL` may be given as `openai/<id>` (Inspect style) or bare.

## 2026-10-16: Refund status `succeeded` renamed to `accepted`
- Context: the first real Paystack refund showed `pending` at Paystack (queued) while our row said `succeeded`. Our status only ever meant that the gateway accepted the request.
- Decision: statuses are `pending` (claimed, outcome unknown), `accepted` (gateway accepted it) and `failed` (gateway definitely rejected it). Settlement is Paystack's state, visible in its dashboard.

## 2026-10-16: Two seeded orders have no Paystack payment
- HM-1019 (₦600,000) and HM-1020 (₦1,299,000) could not be charged in test mode: Paystack returned "Insufficient Balance" for the test card. Both are cases above the ₦300,000 limit that escalate to a human. A human approval on them would be rejected by Paystack and recorded as `failed` by the executor. The setup script originally saved references for these failed charges; fixed to save only successful payments.

## 2026-10-16: Over-promising is checked in code after every decision (reply guard)
- Context: on Day 3, one wording change did not stop Trusted from promising refund amounts; on Day 4 the adaptive attacker drew out new forms (exceptions, claimed actions). The directive says to fix with architecture, not prompt warnings.
- Decision: a guard node after every specialist node. Code decides whether a reply over-promises (`app/reply_guard.py`, pure function, unit tested). The model may rewrite once; if the rewrite still fails, code replaces the reply with a template built from tool results. The model can make a reply better, never riskier.
- Limits, stated: a pattern list catches known phrasings, not all of them. It reduces invented policy; it does not prove its absence.
- Assumption: #1, applied to words rather than money.

## 2026-10-16: Supplementary model swap (gpt-4o-mini)
- Context: on `gpt-5.6-luna` the baseline resisted every attack. To test whether Trusted's guarantees depend on the model, both agents were also run on `gpt-4o-mini`. Labelled supplementary; the main comparison stays on one model, as the directive requires.
- Result: neither model paid out under attack; Trusted's results held on the weaker model; the baseline's policy accuracy fell further.

## 2026-10-16: The headline claim needs Kingsley's decision
- Context: the directive's headline reads "compared with a conventional agent that gave away ₦Y on the same tests". On this suite and both models, the baseline gave away ₦0 under attack; its only payout (₦423,500) came from a routine legitimate request. Writing "gave away ₦423,500 under attack" would be false.
- Options for Kingsley: (a) keep the headline with an accurate qualifier ("gave away ₦423,500 on a routine request it should have sent to a human"); (b) lead with policy accuracy under attack and the R8 bypass; (c) strengthen the attack suite further on Day 5 and report whatever it finds. Not decided by AI.

## 2026-10-18: Headline (Kingsley's decision)
- Kingsley chose the recommended wording, combining options (a) and (b): "Trusted Support resolved 98% of legitimate tickets with no unauthorized refunds. A conventional agent on the same model refunded ₦423,500 that its own rules said needed a human, on an ordinary request with no attack involved, and under attack it told customers rules and promises that do not exist in 88% of conversations."
- Used in README.md, writeup.md and directive.md section 3.
