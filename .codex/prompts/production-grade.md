You are Codex swarm working in repo `maddwiz/moaa-prime`.

MISSION: reach production-grade readiness, end-to-end.
Work continuously until `scripts/check_done.py --criteria .codex/done_criteria.production.json` reports DONE.

Branch and cadence
- Work on branch: `codex/production-grade`.
- Every cycle must ship code, tests, docs, and pushed commits.
- No planning-only cycles.

Primary tracks (all required)
1) Production CI/CD
- Add GitHub Actions workflows:
  - `.github/workflows/ci.yml` for deterministic CI (pytest + core eval checks).
  - `.github/workflows/release.yml` for manual release flow + artifact publish support.
- Keep workflows stable and fast for repeated runs.

2) Runtime hardening
- Implement `scripts/preflight_prod.py` with machine-readable output (`reports/preflight_prod.json`).
- Validate environment, model/provider wiring, filesystem/report paths, and CLI health.
- Add safe timeouts/retries where needed for provider calls and swarm execution.

3) Load and reliability
- Implement `scripts/load_smoke.py` with deterministic load test output (`reports/load_smoke.json`).
- Track request count, failures, error_rate, p50/p95 latency.
- Keep error rate and p95 latency within production criteria budgets.

4) Eval breadth + non-regression
- Expand deterministic eval catalog and maintain category balance.
- Keep pass-rate non-regressive while reducing latency for swarm/dual modes.
- Preserve router and tool-first non-regression guarantees.

5) Operational readiness docs
- Create/update:
  - `PRODUCTION_READINESS.md`
  - `RUNBOOK_PRODUCTION.md`
- Include SLOs, on-call ownership, RTO/RPO, deployment, rollback, incident playbooks.

6) Test coverage for production surfaces
- Add tests:
  - `tests/test_prod_preflight.py`
  - `tests/test_prod_load_smoke.py`
  - `tests/test_prod_report_schema.py`
- Ensure deterministic behavior under stub provider.

Non-negotiables
- Preserve API contracts in `CONTRACTS.md`.
- Keep optional Ollama support intact.
- Keep generated artifacts in `reports/` and gitignored.
- Keep docs in sync with runtime behavior.

Required validation per cycle
- `pytest -q`
- `python scripts/eval_matrix.py`
- `python scripts/eval_router.py`
- `python scripts/eval_dual_gate.py`
- `python scripts/preflight_prod.py --output reports/preflight_prod.json`
- `python scripts/load_smoke.py --output reports/load_smoke.json --iters 50`
- `python scripts/check_done.py --criteria .codex/done_criteria.production.json`

Definition of done
- Only done-check with `.codex/done_criteria.production.json` can declare completion.
- If not done, continue cycling automatically.

Final output required at completion
- concise pass/fail gate summary
- before/after metrics table
- commit hash, branch, and report paths
