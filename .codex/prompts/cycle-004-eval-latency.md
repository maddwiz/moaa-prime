You are Codex swarm working in repo `maddwiz/moaa-prime`.

Mission (Cycle 4)
Deliver a measurable upgrade in evaluation breadth and latency efficiency without sacrificing correctness.

Primary objectives
1) Expand eval coverage
- Grow deterministic eval suites so results are meaningful (math, code, reasoning, safety, routing intent, memory behavior).
- Keep suites CI-friendly and reproducible.
- Standardize report schemas and include explicit counts fields (`num_cases`, `scored_cases`, `passed`).

2) Latency tuning
- Reduce average latency proxy for `swarm` and `dual_gated` modes while keeping pass-rate non-regressive.
- Target: meaningful latency improvement vs current baseline from `reports/eval_matrix.json`.
- Tune swarm rounds, budget profiles, and stop conditions (diminishing returns / early stop).

3) Preserve correctness
- Keep `tool_first` and router non-regression guarantees intact.
- Keep dual-gate trigger behavior bounded and not always-on.

Execution rules
- Use Codex multi-agent mode.
- Make concrete code changes each cycle (no planning-only cycles).
- Keep deterministic defaults and optional Ollama support.
- Preserve contract shapes in `CONTRACTS.md`.
- Update continuity docs when behavior changes.

Required validations per cycle
- `pytest -q`
- `python scripts/eval_matrix.py`
- `python scripts/eval_router.py`
- `python scripts/eval_dual_gate.py`
- `python scripts/check_done.py --criteria .codex/done_criteria.json`

Cycle completion output
- Commit and push changes.
- Print before/after table for pass rate and latency by mode.
- List updated report paths.
