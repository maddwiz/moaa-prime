# Production Readiness

## Scope
This document defines production readiness gates for `moaa-prime` on branch/release builds.  
The scope includes runtime safety, deterministic eval quality, CI/CD repeatability, and operational response posture.

The production control plane for this repository is:
- CI workflow: `.github/workflows/ci.yml`
- Release workflow: `.github/workflows/release.yml`
- Runtime gates: `scripts/preflight_prod.py`, `scripts/load_smoke.py`
- Quality gates: `scripts/eval_matrix.py`, `scripts/eval_router.py`, `scripts/eval_compare.py`, `scripts/eval_dual_gate.py`, `scripts/eval_external_bench.py`

## Service Level Objectives (SLO)
Primary SLO targets for release candidates:

1. Quality SLO
- `eval_matrix` pass criteria remain non-regressive versus baseline:
  - `summary.tool_first.pass_rate_delta_vs_baseline > 0`
  - `summary.swarm.pass_rate_delta_vs_baseline > 0`
  - `summary.dual_gated.pass_rate_delta_vs_baseline >= 0`

2. Reliability SLO
- `preflight_prod` must report `status = pass`.
- `load_smoke` must report:
  - `error_rate <= 0.01`
  - `p95_latency_ms <= 2500`
- `load_smoke_long` (`--iters 500`) must report:
  - `error_rate <= 0.01`
  - `p95_latency_ms <= 2500`

3. Stability SLO
- Router and dual-gate non-regression checks remain passing:
  - routing accuracy delta `>= 0`
  - oracle score gain delta `>= 0`
  - dual trigger rate bounded below full activation
- External holdout benchmark remains healthy:
  - `counts.num_cases >= 100`
  - `metrics.pass_rate >= 0.75`

## Availability and Recovery Targets
- RTO: 30 minutes for production rollback to last known-good release.
- RPO: 15 minutes for generated report artifacts and release metadata.
- These targets assume GitHub Actions and repository access are available.

## On-call Ownership
- Primary On-call: platform/release owner for this repository.
- Secondary On-call: runtime/eval owner.
- Escalation path:
  1. Primary triages failing gate.
  2. Secondary validates runtime/eval impact.
  3. Release manager authorizes Rollback or hotfix promotion.

Minimum on-call responsibilities:
- Monitor CI and release workflow outcomes.
- Confirm `preflight_prod` and `load_smoke` report status for each release candidate.
- Trigger rollback when any production gate is red.

## Runtime Hardening Baseline
Current hardening controls:
- Optional Ollama provider calls include bounded timeout/retry behavior.
- Swarm load smoke execution uses bounded timeout/retry at call-site.
- CLI health and runtime smoke checks are part of preflight validation.

Required runtime checks:
- Environment and provider configuration validation.
- Filesystem/report path write checks.
- CLI invocation health (`python -m moaa_prime --help`).
- Runtime execution sanity (`run_once` smoke path).

## Deployment Readiness Checklist
A candidate is deployable only when all items are true:

1. CI green (`pytest`, eval scripts, preflight, load smoke).
2. Release workflow dry run or manual dispatch succeeds.
3. `scripts/check_done.py --criteria .codex/done_criteria.production.json` returns DONE.
4. Production docs (`PRODUCTION_READINESS.md`, `RUNBOOK_PRODUCTION.md`) match runtime behavior.
5. No contract-breaking changes in `CONTRACTS.md`.

## Release and Rollback Policy
Release policy:
- Releases are created via manual `workflow_dispatch` in `.github/workflows/release.yml`.
- Artifacts are attached to GitHub releases for traceability.

Rollback policy:
- Rollback to previous release tag if any SLO/SLI gate fails post-release.
- Rollback trigger examples:
  - sustained load smoke error-rate breach,
  - p95 latency budget breach,
  - deterministic eval non-regression failure,
  - runtime preflight hard fail in target environment.

Rollback execution:
1. Stop promotion of current candidate.
2. Re-point deployment to last known-good tag.
3. Re-run preflight and smoke checks on rollback target.
4. Open incident ticket and attach failing/passing report diffs.

## Observability and Evidence
Required evidence per release:
- `reports/eval_matrix.json`
- `reports/eval_router.json`
- `reports/eval_compare.json`
- `reports/dual_gated_eval.json`
- `reports/external_bench.json`
- `reports/preflight_prod.json`
- `reports/load_smoke.json`
- `reports/load_smoke_long.json`

Evidence retention:
- Attach release artifact bundle in GitHub release.
- Keep CI logs for audit trail.

## Exit Criteria for Production Grade
Production grade is reached when:
- All required gates pass in a clean worktree.
- All required reports are generated and satisfy thresholds.
- Operational runbook is actionable and current.
- On-call and rollback ownership is explicit.
