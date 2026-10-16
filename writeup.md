# Trusted Support: write-up

<!-- DRAFT for Kingsley's review. Headline framing follows the recommendation in docs/decisions.md (options a and b); change it if you choose otherwise. Bracketed items need your input. -->

**In short:** I built a customer support AI for an online store that can process refunds without being talked into giving money away. The AI handles the conversation; tested code decides every refund, and only that code can move money. Against a conventional agent on the same model and tests, it resolved 98% of legitimate tickets (the conventional agent: 80%), made no unauthorized refunds, and told customers far fewer things the system had not decided. The conventional agent refunded ₦423,500 that its own instructions said needed a human.

## The problem

The support tickets most worth automating involve money, and language models are built to be persuadable; a refund policy must not be. Air Canada was held liable for a refund rule its chatbot invented; a dealership's chatbot "agreed" to sell a car for $1.

I found this building my own support platform, in a popular LangGraph tutorial whose classifier treats every complaint as refundable. Auditing five public support agents confirmed it: in that tutorial the model classified complaints correctly 18 times out of 18, and one line of code, `if "refundable" in output`, sent all 12 non-refundable complaints down the refund path, because "non_refundable" contains "refundable". In OpenAI's own demo, "your agent already promised me" got $280 of vouchers issued in both runs. Where a rule lived in code, attacks failed. Where it lived in a prompt, or in fragile code around the model, the outcome depended on wording.

## What I unlearned

**"Safety lives in the system prompt."** I now put authority in code. The model never supplies an amount; a pure policy engine computes it, signs the decision, and only a separate executor can call the payment gateway. A test drives every tool as a fully compromised model would; money still follows policy. The evidence that broke the old habit came from my own baseline: the store rule "refunds over ₦300,000 need a human" was in its instructions, and on an ordinary cancellation it refunded ₦423,500 anyway, in two of three runs. No attack was involved.

**"Build first, evaluate after."** I wrote the attack suite before the agents existed and committed each new attack set before running it. The first real run found that my own measuring was wrong: the judge could not see what the agent had done, and the scorer let an unnecessary escalation pass. Both were fixed by making the eval stricter.

**"More agents make a stronger system."** One graph, three narrow nodes, depth only on the money path. Its cost showed too: once in three final runs, a return request reached the node with no return tool.

The habit I had to catch myself in: when Trusted promised a customer a full refund on their word that an item was unopened, my first fix was better wording. It did not work. The fix that did is a code check on every reply after a decision, with a template fallback the model cannot make riskier.

## How I used AI

I used Claude Code as the builder throughout, directed by a written directive (`directive.md`). [Day 1: how the directive was drafted.] From Day 2, AI wrote the code, tests, eval suites, audit adapters and documents; I directed scope, made the decisions only I could make, and reviewed. The log records them: building the skeleton before the audit; switching from Stripe to Paystack because Stripe is not available in Nigeria; repricing the store in naira, overruling AI's recommendation to keep dollars; and asking for the log to be backfilled only with what could be evidenced.

AI also made mistakes, and the log keeps them: a test assertion that could never fail, two overwritten audit result files (counts corrected to preserved runs), and API keys printed into a session by loading `.env` with the shell. Each became a working rule in the directive.

The work was more compressed than planned: Day 2 was 2026-10-15, and the work for Days 3 to 5 ran on 2026-10-16. The git history shows the real dates.

## What failed

Day 4 was harder than Day 2. An attacker model with a goal and eight adaptive turns, image injection and cross-capability attacks found: a duplicate return authorization (fixed in the policy engine), over-promising that wording could not fix (fixed with the reply check, which itself needed three test-first iterations), and claims of actions the system never took. What is still open: invented policy is reduced, not solved, since a pattern check misses new phrasings; under the adaptive attacker, 31% of Trusted's conversations still contained something the judge flagged. Every failure, with root cause and fix, is in `docs/failures.md`.

The result that surprised me: on this model the conventional agent did not give money away under attack, across 177 attack conversations. The gap appeared on ordinary requests and in what it told customers: under adaptive pressure, 88% of its conversations contained invented rules, exceptions or promises.

## Results

| | Trusted Support | Conventional agent |
|---|---|---|
| Legitimate tickets resolved correctly | 98% | 80% |
| Unauthorized refunds | 0 | ₦423,500 (routine request, 2 of 3 runs) |
| Unauthorized refunds under attack | 0 | 0 |
| Conversations free of invented policy, adaptive attacker | 69% | 12% |

Zero unauthorized refunds is largely guaranteed by design; what matters is that it stayed useful and accurate.

## Why this matters for MUST's clients

Commerce platforms want support automation they can trust with money, and a prompt cannot give them that. The pattern here (model talks, code decides, every money action signed and executed in one place, evals written before the agent) carries over to any client agent that touches refunds, credits or account changes.
