You are Codex swarm working in repo `maddwiz/moaa-prime`.

MISSION
Reach production confidence by tuning the system against tougher benchmarks.
Stop only when:
`python scripts/check_done.py --criteria .codex/done_criteria.toughbench.json` reports DONE.

Branch
- `codex/production-grade`

What production confidence means in this cycle
1) Harder benchmarks, not just bigger counts
- Build and evaluate a tougher benchmark suite with adversarial and OOD splits.
- Ensure results are balanced by category, and worst-category quality is above floor.

2) Tuning loop that actually improves outcomes
- Add `scripts/tune_production.py` to search safe routing/swarm/dual-gate configs.
- Optimize for a weighted objective: pass-rate first, latency second, stability third.
- Emit `reports/tuning_report.json` with explored configs and `best_config`.

3) Stability and calibration evidence
- Add `scripts/eval_stability.py` (multi-seed repeatability; >=10 seeds).
- Add `scripts/eval_calibration.py` (ECE, Brier, confidence bins).
- Prove the system is not brittle and confidence is meaningful.

4) Long-run reliability
- Run load smoke at 1000 iterations.
- Keep error rate <=1% and p95 within budget.

Required implementation tasks
- Add dataset: `datasets/tough_benchmarks.jsonl` (>=300 cases) with splits:
  - `holdout`
  - `adversarial`
  - `ood`
- Add runner: `scripts/eval_tough_bench.py` -> `reports/tough_bench.json`.
- Add tuning runner: `scripts/tune_production.py` -> `reports/tuning_report.json`.
- Add stability runner: `scripts/eval_stability.py` -> `reports/stability.json`.
- Add calibration runner: `scripts/eval_calibration.py` -> `reports/calibration.json`.
- Add nightly benchmark workflow: `.github/workflows/nightly-bench.yml`.
- Add tests:
  - `tests/test_prod_tough_bench.py`
  - `tests/test_prod_stability.py`
  - `tests/test_prod_calibration.py`
  - `tests/test_prod_tuning_guardrails.py`

Non-negotiables
- Preserve API contracts in `CONTRACTS.md`.
- Preserve optional Ollama support.
- Keep generated artifacts under `reports/` and gitignored.
- No planning-only cycles; every cycle must ship code + tests + docs updates.
- Commit and push each successful cycle.

Cycle validations (must run every cycle)
- `pytest -q`
- `python scripts/tune_production.py --output reports/tuning_report.json`
- `python scripts/eval_matrix.py`
- `python scripts/eval_router.py`
- `python scripts/eval_compare.py`
- `python scripts/eval_dual_gate.py`
- `python scripts/eval_external_bench.py --output reports/external_bench.json`
- `python scripts/eval_tough_bench.py --output reports/tough_bench.json`
- `python scripts/eval_stability.py --output reports/stability.json --seeds 10`
- `python scripts/eval_calibration.py --output reports/calibration.json`
- `python scripts/load_smoke.py --output reports/load_smoke_long.json --iters 1000`
- `python scripts/check_done.py --criteria .codex/done_criteria.toughbench.json`

Required final output
- pass/fail gate summary
- before/after metrics table
- tuned config selected
- commit hash + branch
- report file paths
