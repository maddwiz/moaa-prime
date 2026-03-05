You are Codex swarm working in repo `maddwiz/moaa-prime`.

MISSION
Ship production-grade robustness by making evaluation hard, blind, and regression-resistant.
Stop only when:
`python scripts/check_done.py --criteria .codex/done_criteria.blindbench.json` reports DONE.

Branch
- `codex/production-grade`

Primary objective
The system must prove quality on hard unseen tasks, not only on tuned/internal data.

Required workstreams
1) Locked blind holdout
- Add a locked holdout benchmark set that is never used for tuning.
- Add `scripts/eval_blind_holdout.py` writing `reports/blind_holdout.json`.
- Report must include summary counts, pass rate, worst-category pass rate, and latency.

2) Leakage audit
- Add `scripts/audit_data_leakage.py` writing `reports/leakage_audit.json`.
- Compute exact and near-duplicate overlap between train/tuning traces and holdout.
- Fail the audit when overlap exceeds thresholds.

3) Red-team stress benchmark
- Add adversarial benchmark evaluation script `scripts/eval_redteam.py` writing `reports/redteam_eval.json`.
- Include attack families (prompt injection, contradiction, malformed I/O, tool spoofing, schema drift).
- Output per-attack pass rates and worst-case category.

4) Shadow production benchmark
- Add `scripts/eval_shadow_prod.py` writing `reports/shadow_prod_eval.json`.
- Use anonymized prompt distribution or synthetic proxy matching production shape.
- Compare against baseline mode and report delta.

5) Stronger gating policy
- Update tuning and eval pipeline so final gate uses worst-case metrics, not only averages.
- Keep deterministic default behavior with seeded runs.

6) CI/nightly integration
- Extend nightly benchmark workflow to include blind holdout, leakage audit, and red-team eval.
- Keep runtime practical; use sharding/batching if needed.

Required implementation artifacts
- datasets:
  - `datasets/benchmark_train.jsonl`
  - `datasets/benchmark_holdout_locked.jsonl`
  - `datasets/benchmark_redteam.jsonl`
  - `datasets/benchmark_shadow_prod.jsonl`
- scripts:
  - `scripts/eval_blind_holdout.py`
  - `scripts/audit_data_leakage.py`
  - `scripts/eval_redteam.py`
  - `scripts/eval_shadow_prod.py`
- tests:
  - `tests/test_prod_blind_holdout.py`
  - `tests/test_prod_leakage_audit.py`
  - `tests/test_prod_redteam.py`
  - `tests/test_prod_shadow_eval.py`

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
- `python scripts/eval_tough_bench.py --output reports/tough_bench.json`
- `python scripts/eval_stability.py --output reports/stability.json --seeds 20`
- `python scripts/eval_calibration.py --output reports/calibration.json`
- `python scripts/load_smoke.py --output reports/load_smoke_long.json --iters 1500`
- `python scripts/eval_blind_holdout.py --output reports/blind_holdout.json`
- `python scripts/audit_data_leakage.py --output reports/leakage_audit.json`
- `python scripts/eval_redteam.py --output reports/redteam_eval.json`
- `python scripts/eval_shadow_prod.py --output reports/shadow_prod_eval.json`
- `python scripts/check_done.py --criteria .codex/done_criteria.blindbench.json`

Required final output
- gate summary with failed/passed conditions
- before/after metrics table
- tuned config selected
- commit hash + branch
- report file paths
