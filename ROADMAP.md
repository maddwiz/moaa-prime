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

## PR-7: Telemetry Dashboard (Optional)

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

## Done Definition

MoAA is done when all are true:
1. `pytest -q` is green.
2. `scripts/demo_run.py`, `scripts/bench_run.py`, `scripts/eval_matrix.py`, and `scripts/render_report.py` run cleanly.
3. `reports/eval_matrix.json` shows:
   - tool-first beats baseline,
   - swarm beats baseline where expected,
   - dual-gated does not regress overall.
4. `README.md` and `ROADMAP.md` are complete and current.
5. `reports/final_report.json` is generated and demo-ready.

Autopilot must stop only when done-check criteria are satisfied.
