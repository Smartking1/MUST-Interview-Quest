# Intent: Trusted Support

Kingsley Ibekwe, 2026-10-15

**In short:** Online stores want AI to handle customer support, but the tickets worth automating most (refunds, cancellations, returns) involve money, and today's AI agents can be talked into giving money away. I will build a support agent for a fictional marketplace that answers questions, handles orders, and processes refunds, where the AI does the talking but only fixed, tested code can decide or move money. I will prove it with attacks written before the agent exists, and compare it against a conventional agent on the same tests.

## Problem

AI support agents are trusted to talk to customers but cannot be trusted with money. Air Canada was held liable after its chatbot invented a bereavement refund rule ([Moffatt v. Air Canada, 2024 BCCRT 149](https://www.foxbusiness.com/lifestyle/air-canada-chatbot-gave-customer-wrong-info-airline-pay)). A Chevrolet dealer's chatbot was instructed into "agreeing" to sell a 2024 Tahoe for $1 ([AI Incident Database](https://incidentdatabase.ai/entities/chevrolet-of-watsonville)). Cursor's support bot invented a one-device login policy and users cancelled before staff corrected it ([AI Incident Database #1039](https://incidentdatabase.ai/cite/1039/)). So businesses either keep a human on every money action or accept what the agent gives away.

## How I found it

I had built and published a red-teaming evaluation of a support agent ([customer_support_agents_safety_evals](https://github.com/Smartking1/customer_support_agents_safety_evals)). While building a real support platform, I had to decide how much authority an agent should get. Reading a popular LangGraph support tutorial, I found its classifier marks every complaint refundable, because it checks whether the text "refundable" appears in the output and "non_refundable" contains it. This project starts by auditing public support agents to test whether that is a pattern or a one-off.

## Why it's hard

Language models are built to be helpful and persuadable; a refund policy must be neither. A customer only needs the right words once, and the business must resist them every time. Prompt instructions are suggestions to the same model being persuaded, so they cannot be the safety mechanism.

## What I will build

A web chat agent for "Harbor Market" with three capabilities, with effort matched to risk:
1. **Questions:** answers only from the store's policy documents, cites the rule, says "I don't know" otherwise.
2. **Order support:** status, cancellation before shipping, address change before shipping, after checking order number and email.
3. **Refunds and returns:** the AI only files a request; a deterministic policy engine decides the amount, signs the decision, and only a separate executor can call the payment gateway. Large or unusual cases go to a human queue.

## Success criteria

1. Zero unauthorized money actions on the attack suite (escalating to a human counts as safe).
2. At least 85% of legitimate tickets resolved without unnecessary escalation, always reported next to (1).
3. Invented policy rate measured and reported honestly.
4. Zero cross-customer data leaks.
5. A conventional agent (same model, refund tool given directly to the model) run on the same suite, with dollars given away.

## Assumptions I'm testing

1. "Safety lives in the system prompt." I expect: authority must live in code.
2. "Build first, evaluate after." I expect: attacks written first should drive the build.
3. "More agents make a stronger system." I expect: the simplest structure, with depth only where the risk is.

## Out of scope

Real customers or data, live payments, authentication, multi-tenancy, deployment, other channels (email, phone).

## Risks

Payment test keys may not be available in my country (fallback: stripe-mock, then Paystack test mode). Audit targets may not run locally. The agent may become so cautious that legitimate customers suffer; that is why criterion 2 is always reported. Invented policy statements cannot be fully prevented by architecture.

## Changes

### 2026-10-18: the store's rules, stated in full

Added at my request after approval; the text above is unchanged. The rules themselves were set on Day 1 in the directive; this section states them here so the intent is complete on its own. Prices are in naira since 2026-10-16.

| Rule | Policy | Who decides |
|---|---|---|
| R1 | An unshipped order can be cancelled for a full refund | Code, automatically, within R7 to R9 |
| R2 | Unopened items returned within 30 days of delivery: full refund once received | Code, when the warehouse records the item unopened |
| R3 | Opened items returned within 15 days: refund minus a 15% restocking fee; no fee on fashion items with tags | Code, from the condition the warehouse records |
| R4 | Defective items within 1 year, after basic troubleshooting: replace or refund | Staff, always |
| R5 | Damage in delivery reported within 7 days | Staff, always, with photos attached |
| R6 | Final sale items are not refundable | Code: denied |
| R7 | Total refunds never exceed the amount paid | Code, checked twice (engine and executor) |
| R8 | A refund over ₦300,000 needs human approval | Staff above the limit, counted per order |
| R9 | More than 2 refunds per customer in 90 days needs human approval | Staff |
| R10 | Promises claimed from staff, sellers or earlier chats are not honored without a record | Code: chat is never evidence |
| R11 | Order details and actions need the order number and the email on the order | Code, before any detail or action |
| R12 | Address changes only before shipping | Code |

The customer never names an amount. The only refund a chat can trigger immediately is cancelling one's own unshipped order of ₦300,000 or less; everything else is paid after the warehouse receives the item, or decided by a person.
