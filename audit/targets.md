# Audit targets

Public, open-source customer support agents and official tutorials that can issue refunds, cancel bookings or make policy claims. All are tutorials or demos, not production systems, and are assessed as such. Pinned to the commit read on 2026-10-16. Cloned locally only; nothing was run against a hosted service.

| # | Target | What it is | Commit | Money or policy capability |
|---|---|---|---|---|
| T1 | [Mobius-strip/customer-support-aiagent](https://github.com/Mobius-strip/customer-support-aiagent) | LangGraph support agent for a food delivery app, with a vision model for proof images | `7a63c35d34823bcb65d939869a45d2fb200e19f6` (2025-04-10) | Classifies complaints as refundable, verifies proof and bill images, sets a refund amount |
| T2 | [LangGraph customer support tutorial](https://github.com/langchain-ai/langgraph/blob/23961cff61a42b52525f3b20b4094d8d2fba1744/docs/docs/tutorials/customer-support/customer-support.ipynb) (official, Swiss Airlines example) | Official LangGraph tutorial notebook; the file now redirects to this commit | `23961cff61a42b52525f3b20b4094d8d2fba1744` | Cancels tickets and bookings; answers from a policy document |
| T3 | [openai/openai-cs-agents-demo](https://github.com/openai/openai-cs-agents-demo) | Official OpenAI Agents SDK demo, airline, multi-agent with handoffs | `bd7bfca0f5abf50529370814c3e7c88542011925` (2025-12-11) | Cancels flights, opens compensation cases and issues vouchers |
| T4 | [Bessiedelight/customer-service-agent](https://github.com/Bessiedelight/customer-service-agent) | Companion repo to a Towards AI LangGraph tutorial ("ShopBot") | `3769937dfcded7fd5495b348e1ec710bcfd3fa63` (2026-06-26) | Processes refunds after deterministic gates and human approval |
| T5 | [dbos-inc/dbos-demo-apps, reliable-refunds-langchain](https://github.com/dbos-inc/dbos-demo-apps/tree/5568fc9fdb61a91e6f7cb300ef6f1cd254d219a6/python/reliable-refunds-langchain) | DBOS durable execution demo with a LangGraph refund agent | `5568fc9fdb61a91e6f7cb300ef6f1cd254d219a6` | Processes refunds, with manual review above $1,000 |

Selection: T1 and T2 were named in the directive. T3 to T5 were found by web search on 2026-10-16 for open-source support agents with refund or cancellation tools.
