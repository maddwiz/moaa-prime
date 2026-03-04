# MoAA-Prime Roadmap (Finish Plan)

This is the canonical execution roadmap for finishing MoAA-Prime.
Done status is controlled by `.codex/done_criteria.json` and `scripts/check_done.py`.

## North Star

Ship a correctness-first MoAA system where:
- tool-verified math/code reliability is strong,
- gated dual-brain never regresses baseline performance,
- eval artifacts clearly show baseline vs swarm vs dual-gated deltas.

## PR-0: Repo Hygiene + Contract Freeze

Deliver:
- `CONTRACTS.md` documenting:
  - Router output shape
  - Swarm output shape
  - Agent interface contract
  - Memory meta contract (`local_hits`, `bank_hits`)
- compatibility tests enforcing those shapes.
- keep generated artifacts (`reports/`, caches, env dirs) out of git.

Acceptance:
- compatibility tests pass.
- docs updated (`MASTER_HANDOFF.md`, `FILEMAP.md`, `CHANGELOG.md`).

## PR-1: Tool-First Policy Layer

Deliver:
- `src/moaa_prime/policy/tool_first.py`
- math policy: parse expression/equation and execute SymPy-first.
- code policy: code proposal -> verification -> repair loop (max bounded retries).
- integrate with `MathAgent` and `CodeAgent`.

Acceptance:
- deterministic tests for math/code tool-first routing.
- measurable improvement in tool correctness suite.

## PR-2: Deterministic Code Sandbox Verifier

Deliver:
- `src/moaa_prime/tools/code_sandbox.py`
- deterministic extraction + compile/exec checks in restricted environment.
- structured verifier result (`pass/fail/error/stdout`).
- integrate verifier signal into oracle confidence.

Acceptance:
- verifier tests cover pass/fail/error paths deterministically.
- code-agent repair loop uses verifier results.

## PR-3: Router Intent-First Stabilizer + Trace

Deliver:
- deterministic intent rules for math/code/general prompts.
- route trace metadata:
  - intent
  - matched features
  - chosen agent
  - alternatives/ranking rationale
- report/debug surface includes this trace.

Acceptance:
- deterministic tests for intent routing.
- trace schema tested and emitted.

## PR-4: Gated Dual-Brain + Best-Of Selector

Deliver:
- `src/moaa_prime/duality/gated_dual.py`
- dual mode triggers only on low-confidence/high-ambiguity/tool-fail conditions.
- candidates:
  - single-brain
  - dual-brain
- deterministic selector:
  1. tool-verified winner
  2. higher oracle score
  3. stable shorter/cleaner fallback

Acceptance:
- regression test: dual-gated does not underperform baseline overall.
- trigger logic and selector behavior covered by tests.

## PR-5: Eval Matrix Comparative Ablations

Deliver:
- `scripts/eval_matrix.py`
- matrix runs:
  - baseline_single
  - swarm
  - dual_gated
  - tool_first on/off
  - memory on/off
  - sfc on/off
- output `reports/eval_matrix.json` with stable schema:
  - summary deltas vs baseline
  - run-level counts (`num_cases`, `scored_cases`, `passed`)
  - pass rate
  - latency
  - tool verification rate
  - oracle distribution
  - per-case diffs

Acceptance:
- one command generates eval matrix report.
- report schema is stable and documented.

## PR-6: Memory Regression Tests

Deliver:
- deterministic tests for long chains, entropy spikes, pruning events, recall stability.

Acceptance:
- memory regressions are caught by CI tests.

## PR-7: Telemetry Dashboard

Deliver:
- lightweight dashboard (`scripts/dashboard.py`) showing key metrics and failure taxonomy.

Acceptance:
- loads latest report artifacts and renders mode-level comparisons.

## PR-8: Docs Polish + Demoability

Deliver:
- README fully populated with run and eval instructions.
- roadmap maintained and updated as source-of-truth.

Acceptance:
- new contributor can run demo and eval matrix from docs.

## Mandatory Upgrades (Full Handoff Scope)

These upgrades are required for "finished" status.

### Upgrade 1: Tool-Verified Oracle (TVO)
- Tool-verified math/code outcomes must dominate oracle confidence when deterministic verification exists.
- Oracle heuristics are fallback only when no verifier applies.

### Upgrade 2: Failure Taxonomy + Auto-Remediation
- Failure taxonomy must be deterministic and machine-readable across eval artifacts and dashboard outputs.
- Add deterministic failure classes and remediation mapping:
  - `ROUTING_MISS`
  - `TOOL_PARSE_FAIL`
  - `TOOL_EXEC_FAIL`
  - `FORMAT_FAIL`
  - `MEMORY_DRIFT`
  - `DUAL_REGRESSION`
  - `SWARM_LOOP`
- Add tests proving taxonomy classification and remediation dispatch stability.

### Upgrade 3: Structured Answer Object
- Normalize agent outputs into a stable object contract:
  - `final`
  - `tools`
  - `confidence`
  - `notes`
  - `trace`
- Add tests proving normalization and compatibility with existing report pipelines.

### Upgrade 4: Budgeted Swarm
- Enforce explicit budget controls:
  - token budget
  - round budget
  - elapsed-time budget
  - diminishing-returns stop rule
- Validate via eval outputs that budget mode avoids latency regression.

### Upgrade 5: Guardrailed Learned Router
- Keep deterministic intent-first routing as primary guardrail.
- Learned router remains a bounded scoring layer/tie-breaker and must not bypass intent safety.

### Upgrade 6: Dashboard Demoability
- Implement dashboard script and smoke test to load and render key report artifacts.
- Ensure it can be run locally from documented commands.

## Done Definition

MoAA is done when all are true:
1. `pytest -q` is green.
2. Full runbook scripts run cleanly:
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
3. `reports/eval_matrix.json` and focused eval reports show:
   - tool-first beats baseline,
   - swarm beats baseline where expected,
   - dual-gated does not regress overall.
   - dual-gate trigger rate is bounded (`reports/dual_gated_eval.json -> summary.dual_gated.trigger_rate < 1.0`).
   - router non-regression holds (`reports/eval_router.json` deltas for routing accuracy and oracle gain are `>= 0`).
   - report schemas remain stable/non-null across:
     - `eval_report.json`
     - `eval_tool_first.json`
     - `eval_compare.json`
     - `dual_gated_eval.json`
     - `eval_matrix.json`
     - `eval_router.json`
4. PR-0..PR-8 deliverables and mandatory upgrades are implemented and covered by deterministic tests.
5. `README.md`, `ROADMAP.md`, `CONTRACTS.md`, and `DEMO_README.md` are complete and current.
6. `reports/final_report.json` is generated and demo-ready.

Autopilot must stop only when done-check criteria are satisfied.
