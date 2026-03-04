You are working in repo `maddwiz/moaa-prime`.

Objective:
Finish MoAA-Prime by implementing and hardening the full handoff scope end-to-end. Completion means everything in the finish handoff is implemented and working, not just partial roadmap milestones.

Execution policy:
- Use Codex multi-agent mode for implementation work.
- Complete one PR-sized roadmap item per cycle with tests + reports + docs.
- Keep API contracts stable; no silent schema drift.
- Keep changes safe, incremental, and test-backed.
- Do not stop at planning; ship concrete code each cycle.

Roadmap priority (must follow in order):
1. PR-0: repo hygiene + contract freeze (`CONTRACTS.md` + compatibility tests).
2. PR-1: tool-first policy layer for math/code correctness.
3. PR-2: deterministic code sandbox verify + repair loop integration.
4. PR-3: router intent-first stabilizer + route trace metadata.
5. PR-4: gated dual-brain best-of selector (no blind dual mode).
6. PR-5: eval matrix comparative ablations with machine-readable summary.
7. PR-6: memory regression tests (long chains / entropy spikes / pruning / recall stability).
8. PR-7: dashboard + telemetry view for eval outputs.
9. PR-8: docs and demo polish aligned with actual runnable commands.

Mandatory upgrades (treat as required, not optional):
- Tool-Verified Oracle behavior (tool-verified outcomes dominate oracle confidence when available).
- Failure taxonomy + deterministic remediation loop (`ROUTING_MISS`, `TOOL_PARSE_FAIL`, `TOOL_EXEC_FAIL`, `FORMAT_FAIL`, `MEMORY_DRIFT`, `DUAL_REGRESSION`, `SWARM_LOOP`).
- Structured Answer Object normalization for stable downstream grading/reporting.
- Budgeted swarm behavior with explicit time/token/round limits and diminishing-returns stop.
- Learned router remains guardrailed by deterministic intent-first routing.
- Dashboard script for human-readable report navigation.

Non-negotiables:
- Preserve API shapes documented in `CONTRACTS.md`.
- Keep tests green at all times.
- Keep generated outputs gitignored.
- Optional Ollama support must remain intact.

Required cycle outputs:
- code changes
- tests and/or compatibility assertions
- updated docs (`MASTER_HANDOFF.md`, `FILEMAP.md`, `CHANGELOG.md`)
- one commit with a clear message

Required validation before finishing a cycle:
- `pytest -q`
- run relevant scripts for touched subsystems
- for finish-gate progress, keep these passing:
  - `scripts/demo_run.py`
  - `scripts/bench_run.py`
  - `scripts/eval_run.py`
  - `scripts/eval_tool_first.py`
  - `scripts/eval_compare.py`
  - `scripts/eval_dual_gate.py`
  - `scripts/eval_matrix.py`
  - `scripts/train_router.py`
  - `scripts/eval_router.py`
  - `scripts/render_report.py`

Definition of done:
- determined by `.codex/done_criteria.json` and enforced by `scripts/check_done.py`.
- do not claim completion manually; only the done-check gate can finalize.
