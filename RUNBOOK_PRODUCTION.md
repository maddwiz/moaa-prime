# Runbook Production

## Purpose
This Runbook defines standard operating procedures for production validation, release, incident response, and rollback for `moaa-prime`.

It is written for operators who need deterministic, repeatable commands with clear go/no-go checkpoints.

## Preconditions
Before running any production command:
- Work from a clean branch (`git status --porcelain` must be empty).
- Use Python from `.venv` when available.
- Ensure `MOAA_LLM_PROVIDER` is set intentionally (`stub` by default; `ollama` optional).

## Standard Validation Sequence
Run these commands in order from repo root:

1. `pytest -q`
2. `python scripts/eval_matrix.py`
3. `python scripts/eval_router.py`
4. `python scripts/eval_compare.py`
5. `python scripts/eval_dual_gate.py`
6. `python scripts/eval_external_bench.py --output reports/external_bench.json`
7. `python scripts/preflight_prod.py --output reports/preflight_prod.json`
8. `python scripts/load_smoke.py --output reports/load_smoke.json --iters 50`
9. `python scripts/check_done.py --criteria .codex/done_criteria.production.json`

Expected result:
- Final command returns DONE and all previous commands exit successfully.

## Smoke Procedure
Use Smoke checks for fast runtime confidence after changes:

1. `python scripts/preflight_prod.py --output reports/preflight_prod.json`
2. `python scripts/load_smoke.py --output reports/load_smoke.json --iters 20`

Smoke pass criteria:
- `reports/preflight_prod.json` has `status = pass`.
- `reports/load_smoke.json` has:
  - `metrics.error_rate <= 0.01`
  - `metrics.p95_latency_ms <= 2500`

## Long-Eval Procedure
Use this sequence for production campaign/soak verification:

1. `python scripts/eval_matrix.py`
2. `python scripts/eval_router.py`
3. `python scripts/eval_compare.py`
4. `python scripts/eval_dual_gate.py`
5. `python scripts/eval_external_bench.py --output reports/external_bench.json`
6. `python scripts/load_smoke.py --output reports/load_smoke_long.json --iters 500`
7. `python scripts/check_done.py --criteria .codex/done_criteria.longevals.json`

Long-eval pass criteria:
- matrix counts: `summary.counts.num_cases >= 1200`
- router/compare counts: `>= 50`
- dual baseline counts: `>= 150`
- external holdout: `counts.num_cases >= 100` and `metrics.pass_rate >= 0.75`
- long smoke: `request_count >= 500`, `error_rate <= 0.01`, `p95_latency_ms <= 2500`

## Release Procedure
Release is manual by design to keep control explicit.

1. Confirm local validation sequence is green.
2. Push branch and open/refresh PR.
3. In GitHub Actions, trigger `Release` workflow (`workflow_dispatch`).
4. Provide:
  - `tag` (required)
  - `release_name` (optional)
5. Wait for:
  - pytest and eval gates,
  - preflight/load checks,
  - artifact bundle upload,
  - GitHub release artifact publish.

Release success criteria:
- Workflow exits green.
- Release artifact is attached to the target tag.

## Incident Runbook
Use this Incident flow when production gates fail or behavior regresses.

1. Classify incident severity.
2. Capture first failing signal:
  - CI log, release log, or report diff.
3. Identify failing gate type:
  - Contract/schema break
  - Eval non-regression break
  - Runtime preflight fail
  - Load reliability/latency fail
4. Assign owner:
  - Primary On-call handles containment.
  - Secondary On-call validates remediation.
5. Decide mitigation:
  - hotfix forward, or
  - Rollback to last known-good release.

## Rollback Procedure
Rollback is mandatory when release health is uncertain or SLO breach is confirmed.

1. Select previous stable release tag.
2. Re-point deployment to that tag.
3. Run post-rollback Smoke:
  - `python scripts/preflight_prod.py --output reports/preflight_prod.json`
  - `python scripts/load_smoke.py --output reports/load_smoke.json --iters 20`
4. Verify:
  - preflight status pass,
  - low error rate,
  - p95 latency within budget.
5. Document rollback in incident record with timestamps and report links.

## Troubleshooting Playbooks
### Preflight failure
- Check `checks[*].name` and `checks[*].details` in `reports/preflight_prod.json`.
- Common root causes:
  - invalid provider env,
  - CLI import/runtime issue,
  - filesystem permissions.
- Action:
  - fix failing subsystem,
  - rerun preflight,
  - do not continue to release until status pass.

### Load smoke failure
- Inspect:
  - `metrics.failures`,
  - `metrics.error_rate`,
  - `metrics.p95_latency_ms`,
  - failed sample details.
- Common root causes:
  - runtime exceptions,
  - timeout budget too strict for environment,
  - recent performance regression.
- Action:
  - reproduce with lower `--iters`,
  - isolate failing prompt/sample,
  - patch and rerun full load smoke.

### Eval non-regression failure
- Compare the failing metric with baseline in the target report.
- Validate category-level drift in `eval_matrix` summaries.
- Re-run deterministic eval commands to confirm reproducibility.

## RTO/RPO Operating Targets
- RTO: 30 minutes to restore via Rollback.
- RPO: 15 minutes for release/report artifact recovery.

If RTO or RPO is at risk, escalate immediately to release owner and incident commander.

## Runbook Maintenance
- Update this Runbook whenever scripts, gates, thresholds, or workflow behavior changes.
- Keep command examples exact and copy/paste safe.
- Validate updates in CI before promoting release candidates.
