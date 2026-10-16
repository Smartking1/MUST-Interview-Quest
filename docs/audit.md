# Audit of public customer support agents

**Status: code review complete; runtime attacks pending.** The runtime half needs an LLM API key, which was not yet available when this was written. Findings below are from reading the code at the pinned commits. Nothing here claims a runtime result until one has been observed.

## Summary

Five public support agents (two named in advance, three found by search) were read at pinned commits. All are tutorials or demos, built to teach a framework, not to run a store, and none claims to be production ready.

The pattern across them: where an agent has a money or cancellation action, **the eligibility rule usually lives in the prompt or in model output, not in code**. Two of the five (T4, T5) take refund amounts from the database and put a human in front of large refunds, which is the right instinct. Of the three that issue refunds (T1, T4, T5), none checks the customer's identity in code. T2 ties every action to a server-side passenger identity. T3's identity handling has not yet been reviewed.

## Method

1. Pin each target to a commit (`audit/targets.md`).
2. Read the code path from customer message to money or cancellation action. Record where each decision is made: in code, in the prompt, or in model output.
3. (Pending) Run the core attack conversations locally against each target, with minimal adapters in `audit/harness/`. Every change to a target's code is documented. No hosted services. 45 minutes per target to get it running, 4 hours in total.

## Code review findings

### T1 Mobius-strip/customer-support-aiagent
- **Every complaint is classified refundable.** `nodes.py:66` sets the class with `if "refundable" in classification_raw.lower()`. The model is told to answer `refundable` or `non_refundable`, and `"non_refundable"` contains `"refundable"`, so both answers route to the refund path. This is the observation that started this project, now confirmed at the pinned commit.
- **Proof verification passes unless the vision model replies exactly "no".** `problem_verify` sets `verified = response.lower() != "no"`. A reply such as "No." or "No, the image shows a receipt" counts as verified. (To confirm at runtime.)
- **The refund amount comes from the customer's own image.** `bill_amount_verification` asks the vision model to read the price from a bill photo the customer uploads, and uses that number. There is no order database to check it against, so the customer's image sets the amount.
- No identity check: the flow has no customer or order lookup.

### T2 LangGraph customer support tutorial (official)
- **Identity and ownership are enforced in code.** The passenger ID comes from server-side config, and `cancel_ticket` checks the ticket belongs to that passenger before acting. This is the strongest identity design of the five.
- **No refund tool.** Cancellation deletes the ticket; any fee or refund rule is only in the policy text the model reads via `lookup_policy`. So the risk here is policy claims (what the agent tells the customer about refunds and fees), not payouts.

### T3 openai/openai-cs-agents-demo (official)
- **Voucher amounts come from data, not the model.** `issue_compensation` takes voucher values from the itinerary record. Good.
- **Eligibility lives in the prompt.** The "delay over 3 hours or missed connection" condition appears only in the FAQ text and agent instructions. The tool itself does not check the delay before opening a case and issuing vouchers.
- **Cancellation has no eligibility check** in `cancel_flight`.
- The demo includes LLM-based relevance and jailbreak guardrails, which are a prompt-level defense.

### T4 Bessiedelight/customer-service-agent (Towards AI tutorial)
- **The best design of the five for money.** Deterministic gates in `gates.py` check the order ID format, existence, delivered status and a $500 cap; the amount comes from the database; and a human approves every refund through a LangGraph interrupt.
- **No identity check.** An order ID alone is enough to request a refund, and IDs follow the pattern `ORD-` plus three digits.
- **Delivered means eligible.** No return window or condition rules.
- Cost of the design: a human approves every refund, the trade-off the directive describes (safe, but most of the value of automation is lost).

### T5 dbos-inc reliable-refunds-langchain
- **Amount from the database, and a code-enforced review threshold** ($1,000), with durable workflows. Good.
- **No eligibility check.** `process_refund` approves any order under $1,000 without checking status, time since purchase, or whether it was already refunded.
- **No identity concept.** The purchases table has no customer field; this is a single-user durability demo, so cross-customer leaks are not applicable.
- The agent has a tool that lists every purchase in the database.

## Runtime results

Pending. Planned per target: unauthorized refunds or commitments, invented policies, data leaks, or N/A where the capability does not exist.
