# Trusted Support: write-up

**In short:** I built a customer support AI for an online store that can process refunds without being talked into giving money away: the AI handles the conversation, and tested code decides every refund. It resolved 98% of legitimate tickets with no unauthorized refunds. A conventional agent on the same model refunded ₦423,500 that its own rules said needed a human, on an ordinary request with no attack involved, and under attack it told customers rules and promises that do not exist in 88% of conversations.

## The problem

The support tickets most worth automating involve money, and language models are built to be persuadable; a refund policy must not be. Air Canada was held liable for a refund rule its chatbot invented; a dealership's chatbot "agreed" to sell a car for $1.

I found this building my own support platform, in a popular LangGraph tutorial whose classifier treats every complaint as refundable. Auditing five public support agents confirmed the pattern. In that tutorial the model classified complaints correctly 18 times out of 18, and one line of code, `if "refundable" in output`, sent all 12 non-refundable complaints down the refund path, because "non_refundable" contains "refundable". In OpenAI's own demo, "your agent already promised me" got $280 of vouchers issued in both runs. Where a rule lived in code, attacks failed; where it lived in a prompt, the outcome depended on wording.

## The store's rules

Harbor Market, a fictional Nigerian marketplace, has twelve rules (`policy/policy.md`). The policy engine enforces each one in code:

| Rule | Policy | What the system does |
|---|---|---|
| R1 | Unshipped orders can be cancelled for a full refund | Refunds automatically, subject to R7 to R9 |
| R2 | Unopened returns within 30 days: full refund once received | Authorizes the return; pays when the warehouse records it unopened |
| R3 | Opened returns within 15 days: refund minus 15% (no fee on fashion with tags) | Pays on receipt, from the condition the warehouse records |
| R4 | Defective items within 1 year: replace or refund | Always sends to staff |
| R5 | Delivery damage reported within 7 days | Always sends to staff, with any photo |
| R6 | Final sale items are not refundable | Denies |
| R7 | Refunds never exceed the amount paid | Checked by the engine and again by the executor; each item refunded once |
| R8 | A refund over ₦300,000 needs a human | Cumulative per order, so split claims still escalate |
| R9 | More than 2 refunds in 90 days needs a human | Escalates |
| R10 | Claimed promises are not honored without a record | Nothing said in chat counts as evidence |
| R11 | Order number and email required | Checked in code before any detail or action |
| R12 | Address changes only before shipping | Changes automatically if unshipped |

The customer never names an amount. The only refund a chat can trigger immediately is cancelling one's own unshipped order of ₦300,000 or less; returns pay only after the warehouse receives them, and everything else waits for a person.

## How it differs from a conventional agent

Both agents use the same model, policy and capabilities. The difference is who decides:

| | Conventional agent | Trusted Support |
|---|---|---|
| Refund amount | Chosen by the model | Computed by code; the model's tool has no amount field |
| Path to the payment gateway | The model's refund tool | Only a signed decision, through one executor |
| Rules, limits, identity | Instructions in the prompt | Enforced in code |
| Photos | Seen by the model | Never seen by the model; sent to staff |
| If the model is fooled | It can pay any amount | It can only ask; code refuses |

When the model behaves, both usually agree. When it does not, the conventional agent's mistake is a payment; Trusted Support's is a request the code turns down.

## What I unlearned

**"Safety lives in the system prompt."** Authority now lives in code, as the table above shows. A test drives every tool as a fully compromised model would, and money still follows policy. My own baseline supplied the evidence: "refunds over ₦300,000 need a human" was in its instructions, and on an ordinary cancellation it refunded ₦423,500 anyway.

**"Build first, evaluate after."** The attack suite came before the agents, and every new attack set was committed before it ran. The first real run showed my measuring was wrong: the judge could not see what the agent did, and the scorer let an unnecessary escalation pass. I fixed both by making the eval stricter.

**"More agents make a stronger system."** One graph, three narrow nodes, depth only on the money path. The cost appeared once in three final runs, when a return request reached a node with no return tool; that node can now file returns.

The habit I caught myself in: when Trusted promised a full refund on a customer's word that an item was unopened, my first fix was better wording. It failed. What worked is a code check on every reply after a decision, with a template fallback the model cannot make riskier.

## How I used AI

On Day 1 I spent about five hours with Claude (web version) working out the problem and solution, which became the directive (`directive.md`). From Day 2, Claude Code wrote the code, tests, evals, audit adapters and documents; I directed scope, made the calls only I could make, and reviewed. The log records them: building the core before the audit, switching from Stripe to Paystack because Stripe is not available in Nigeria, repricing the store in naira against AI's recommendation, and choosing the headline.

The schedule was compressed: Day 2 ran on 2026-10-15, Days 3 to 5 on 2026-10-16, and the final documents on 2026-10-18. The git history shows those dates.

## What failed

Day 4 was harder than Day 2. An attacker model with a goal and eight adaptive turns, plus image injection and cross-capability attacks, found a duplicate return authorization (fixed in the policy engine), over-promising that wording could not fix (fixed with the reply check, which needed three test-first iterations), and claims of actions the system never took. Still open: invented policy is reduced, not solved; a pattern check misses new phrasings, and under the adaptive attacker 31% of Trusted's conversations still had something flagged. A re-run of the adaptive suite was cut short when the API account ran out of credits. Every failure is in `docs/failures.md`.

The surprise: on this model the conventional agent gave nothing away under attack, across 177 attack conversations. The gap was on ordinary requests and in what it told customers.

## Results

Final runs, 474 conversations, same model for both agents:

| | Trusted Support | Conventional agent |
|---|---|---|
| Legitimate tickets resolved correctly | 98% | 80% |
| Unauthorized refunds | 0 | ₦423,500 on a routine request (2 of 3 runs; 3 of 3 in a re-run) |
| Unauthorized refunds under attack | 0 | 0 |
| Conversations free of invented policy, adaptive attacker | 69% | 12% |

Zero unauthorized refunds is largely guaranteed by design; what matters is that the agent stayed useful and accurate.

## Why this matters for MUST's clients

Commerce platforms want support automation they can trust with money, and a prompt cannot give them that. The pattern here (the model talks, code decides, every money action is signed and executed in one place, evals come before the agent) applies to any client agent that touches refunds, credits or account changes.
