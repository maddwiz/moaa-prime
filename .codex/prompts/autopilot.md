You are working in repo `maddwiz/moaa-prime`.

Objective:
Continuously move MoAA-Prime forward until the system is production-ready, with deterministic tests and updated continuity docs.

Execution policy:
- Use Codex multi-agent mode for implementation work.
- Choose the single highest-impact backlog item, complete it end-to-end, then commit.
- Keep changes safe, incremental, and test-backed.
- Do not stop at planning; ship concrete code each cycle.

Backlog priority (top to bottom):
1. Strengthen RouterV3 learning quality and calibration.
2. Improve SwarmV3 candidate quality and Pareto selection behavior.
3. Improve GCEL contract evolution quality gates.
4. Expand eval datasets and metrics quality for v2 vs v3 comparisons.
5. Harden CLI/demo scripts and reporting reliability.
6. Improve docs and runbooks to match actual behavior.

Required cycle outputs:
- code changes
- tests or validation updates
- docs updates when behavior changed
- one commit with a clear message

Required validation before finishing:
- `pytest -q`
- run relevant scripts for any changed subsystem

Constraints:
- deterministic default behavior
- optional Ollama support remains intact
- avoid broad risky refactors
