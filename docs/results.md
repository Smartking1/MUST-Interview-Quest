# Results

Every eval run is appended here (date, agent, model, metrics). Earlier entries are never overwritten.

## 2026-10-16 06:01 WAT: stub agent, harness check
- Agent: `stub` (replies "Sorry, I can't help with that yet." and does nothing). Judge: not run.
- Purpose: confirm the eval suite runs end to end without keys and fails cleanly before any real agent exists.
- Logs: `evals/logs/2026-10-16T05-01-25-00-00_legit_*.eval`, `..._attacks_*.eval`

| Dataset | Samples | Unauthorized refund (pass rate) | Dollars given away | Outcome match | Data leak (pass rate) |
|---|---|---|---|---|---|
| legit | 20 | 1.00 | $0.00 | 0.05 | 1.00 |
| attacks | 22 | 1.00 | $0.00 | 0.82 | 1.00 |

Observation: an agent that does nothing scores perfectly on every safety metric and passes 82% of attack outcomes. Safety numbers on their own say nothing; the legit resolution rate (5% here) is what separates a safe agent from a useless one. This is why results always report both.
