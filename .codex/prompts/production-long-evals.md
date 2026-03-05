You are Codex swarm working in repo `maddwiz/moaa-prime`.

MISSION: run a long-eval production campaign and keep iterating until done.
Stop only when:
`python scripts/check_done.py --criteria .codex/done_criteria.longevals.json` returns DONE.

Branch
- `codex/production-grade`

Required outcomes
1) Long eval volume
- Expand deterministic eval volume so report counts hit long-eval thresholds.
- `eval_matrix` total case volume must be large and category-balanced.
- `eval_router`, `eval_compare`, and `eval_dual_gate` suites must also run at long volume.

2) External holdout benchmark
- Add `datasets/external_benchmarks.jsonl` with at least 100 holdout cases.
- Include metadata fields: `case_id`, `category`, `prompt`, `expected`, `split` (`holdout`), and source metadata.
- Add `scripts/eval_external_bench.py` to score this dataset and emit `reports/external_bench.json`.
- Add deterministic tests for this path.

3) Long load smoke
- Run 500-iteration smoke load and emit `reports/load_smoke_long.json`.
- Keep error rate and p95 latency within production gate budgets.

4) Preserve quality
- Keep existing production non-regression guarantees (tool-first/router/dual-gate contracts).
- Keep generated artifacts gitignored under `reports/`.

5) Keep docs current
- Update `MASTER_HANDOFF.md`, `FILEMAP.md`, `CHANGELOG.md`, `PRODUCTION_READINESS.md`, and `RUNBOOK_PRODUCTION.md` when behavior changes.

Execution style
- Multi-agent implementation every cycle.
- No planning-only cycles.
- Commit and push each successful cycle.

Required validation each cycle
- `pytest -q`
- `python scripts/eval_matrix.py`
- `python scripts/eval_router.py`
- `python scripts/eval_compare.py`
- `python scripts/eval_dual_gate.py`
- `python scripts/eval_external_bench.py --output reports/external_bench.json`
- `python scripts/load_smoke.py --output reports/load_smoke_long.json --iters 500`
- `python scripts/check_done.py --criteria .codex/done_criteria.longevals.json`

Final output on completion
- pass/fail gate summary
- before/after metric table
- commit hash + branch
- report file paths
