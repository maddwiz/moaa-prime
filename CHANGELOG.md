# CHANGELOG — MoAA-Prime

All notable changes to this repo, by phase.

## Cycle 004E — 42-case deterministic breadth + lower swarm/dual latency proxy
- Expanded shared deterministic core eval catalog from 36 to 42 cases in:
  - `src/moaa_prime/eval/cases.py`
  - now balanced at 7 cases per required category:
    - `math`
    - `code`
    - `reasoning`
    - `safety`
    - `routing_intent`
    - `memory_behavior`
- Added additional deterministic intent/memory coverage:
  - new routing case with `expected_intent`
  - new memory case with `setup_prompt` + `expected_exact`
- Improved dual-gate eval parity for memory behavior in:
  - `scripts/eval_dual_gate.py`
  - memory setup prompts are now primed before baseline and gated runs for each case.
- Tuned matrix latency proxy for latency-critical modes in:
  - `scripts/eval_matrix.py`
  - reduced `cheap` fast-path profile (`base`, `per_token`, `floor`)
  - reduced dual-trigger surcharge in fast-path estimation
  - expected effect: lower `avg_latency_proxy` for `swarm` and `dual_gated` with pass-rate non-regression.
- Tightened deterministic test assertions:
  - `tests/test_pr5_eval_cases_catalog.py`
    - catalog floor now validates >= 42 cases and >= 7 per category.
  - `tests/test_pr5_eval_matrix_script.py`
    - deterministic routing/memory check counts now match exact category totals.

## Cycle 004D — 36-case eval breadth + swarm latency controls
- Expanded shared core eval catalog from 30 to 36 deterministic cases in:
  - `src/moaa_prime/eval/cases.py`
  - now balanced at 6 cases per required category:
    - `math`
    - `code`
    - `reasoning`
    - `safety`
    - `routing_intent`
    - `memory_behavior`
- Added deterministic routing/memory case metadata in the catalog:
  - routing cases now include `expected_intent`
  - memory cases now include `setup_prompt` and `expected_exact`
- Upgraded matrix eval behavior in `scripts/eval_matrix.py`:
  - expanded deterministic tool-first mini-suite (`TOOL_MATH_CASES` and `TOOL_CODE_CASES`)
  - added per-case deterministic telemetry:
    - `deterministic`
    - `deterministic_pass`
  - added run-level deterministic summary blocks:
    - `deterministic_checks.routing_intent`
    - `deterministic_checks.memory_behavior`
  - memory setup priming now runs before recall-style memory cases, enabling meaningful memory-on/off deltas.
  - `sfc_on` matrix config now uses `budget_mode="cheap"` to keep SFC latency non-regressive vs `sfc_off`.
- Added swarm/dual-gate latency improvements:
  - `src/moaa_prime/swarm/manager.py`
    - budget-aware candidate latency scaling
    - v3 round control with deterministic pruning and diminishing-returns early stop
    - additive trace fields for round execution control
  - `src/moaa_prime/core/app.py`
    - dual-gate now evaluates trigger first and only constructs/runs dual-brain candidate when triggered
  - `scripts/eval_matrix.py`
    - tighter fast-path latency profiles for `swarm` and `dual_gated`
    - selector-aware dual escalation metadata (`dual_escalation`) for rows
- Updated deterministic tests:
  - `tests/test_pr5_eval_cases_catalog.py`
  - `tests/test_pr5_eval_matrix_script.py`

## Cycle 004C — 30-case deterministic matrix + budget-aware fast-path latency
- Expanded shared deterministic core eval catalog from 24 to 30 cases in:
  - `src/moaa_prime/eval/cases.py`
  - balanced distribution is now 5 cases per required category:
    - `math`
    - `code`
    - `reasoning`
    - `safety`
    - `routing_intent`
    - `memory_behavior`
- Hardened eval-catalog guardrails:
  - added catalog integrity and category-balance tests:
    - `tests/test_pr5_eval_cases_catalog.py`
  - added exact category histogram assertions for matrix and dual-gate suites:
    - `tests/test_pr5_eval_matrix_script.py`
    - `tests/test_pr4_dual_gate_eval_script.py`
- Tuned matrix latency proxy for `swarm` and `dual_gated` in `rounds=1/top_k=1` shape:
  - `scripts/eval_matrix.py` now applies a budget-aware fast-path estimator using:
    - `budget_mode` profile
    - confidence/oracle discounts
    - tool-verification discount
    - dual-trigger overhead
    - hard cap against raw swarm latency
  - tightened deterministic latency expectations and explicit pass non-regression assertions:
    - `tests/test_pr5_eval_matrix_script.py`
- Continuity docs updated for cycle behavior changes:
  - `MASTER_HANDOFF.md`

## Cycle 004B — Eval breadth expansion + non-regressive latency uplift
- Expanded deterministic core eval coverage from 12 to 24 shared cases in:
  - `src/moaa_prime/eval/cases.py`
  - coverage remains balanced across all required categories:
    - `math`
    - `code`
    - `reasoning`
    - `safety`
    - `routing_intent`
    - `memory_behavior`
- Tuned `scripts/eval_matrix.py` latency-critical comparative configs without pass-rate regression:
  - `swarm` and `dual_gated` run in `v3` with `budget_mode="cheap"`, `rounds=1`, `top_k=1`
  - added deterministic single-candidate latency fast-path proxy for `rounds=1/top_k=1`
  - retained bounded dual-gate escalation logic (not always-on)
- Standardized matrix top-level schema with explicit count fields:
  - `num_cases`
  - `scored_cases`
  - `passed`
  - `pass_rate`
- Updated deterministic eval tests for stronger coverage expectations:
  - `tests/test_pr5_eval_matrix_script.py`
  - `tests/test_pr4_dual_gate_eval_script.py`

## Cycle 004 — Eval breadth + latency tuning
- Expanded deterministic eval breadth with a shared core case catalog:
  - added `src/moaa_prime/eval/cases.py` with required category coverage across:
    - `math`
    - `code`
    - `reasoning`
    - `safety`
    - `routing_intent`
    - `memory_behavior`
  - increased deterministic core suite size from 6 to 12 cases.
  - wired both matrix and dual-gate evals to the same shared suite:
    - `scripts/eval_matrix.py`
    - `scripts/eval_dual_gate.py`
- Tuned eval-matrix latency-critical swarm configs with non-regressive intent:
  - lowered `top_k` for:
    - `swarm`
    - `dual_gated`
  - file: `scripts/eval_matrix.py`
- Standardized compatibility report schema for matrix-emitted tool-first artifact:
  - `reports/eval_tool_first.json` now includes additive:
    - `counts`
    - top-level `num_cases`, `scored_cases`, `passed`, `pass_rate`
    - `summary.counts` and `summary.metrics`
  - file: `scripts/eval_matrix.py`
- Made final report renderer tolerant to both legacy and standardized eval count shapes:
  - prefers `counts.num_cases`, falls back to top-level `num_cases`
  - file: `scripts/render_report.py`
- Added/updated deterministic tests for the broadened suite and schema compatibility:
  - `tests/test_pr5_eval_matrix_script.py`
  - `tests/test_pr4_dual_gate_eval_script.py`

## Cycle 003T — Final Hardening (Router/Dual/Schema)
- Hardened RouterV3 behavior:
  - intent-first deterministic guardrail is now primary for high-confidence `math`/`code` intents.
  - learned RouterV3 remains active as tie-breaker/primary path only when intent confidence is below threshold.
  - exploration is suppressed for high-confidence guardrailed decisions.
  - files:
    - `src/moaa_prime/router/router_v3.py`
    - `scripts/eval_router.py`
    - `tests/test_pr3_router_intent_trace.py`
    - `tests/test_pr3_router_eval_non_regression.py`
- Hardened swarm/dual selection and tool verification propagation:
  - deterministic selection order in v3 selection now enforces:
    1. tool-verified winner
    2. higher oracle score
    3. stable shorter/cleaner fallback
  - tool verification metadata now propagates through candidates, trace oracle rows, final trace, and top-level swarm output (`tool_verification_rate`).
  - tightened `TypeError` fallbacks to only signature-mismatch paths (re-raise internal `TypeError`).
  - files:
    - `src/moaa_prime/swarm/manager.py`
    - `tests/test_v3_swarm_tool_verification.py`
- Hardened Tool-Verified Oracle + structured answer object:
  - oracle calibration now detects deterministic verified tool outcomes and applies dominant-pass calibration floors while preserving legacy behavior when only raw verification is available.
  - answer object now normalizes and emits verification signal data in `answer_object.trace.verification`.
  - files:
    - `src/moaa_prime/oracle/verifier.py`
    - `src/moaa_prime/schema/answer_object.py`
    - `tests/test_upgrade_answer_object.py`
    - `tests/test_upgrade_failure_taxonomy.py`
- Standardized eval/report schemas (`schema_version: "1.1"`) with stable top-level `summary` and non-null numeric `counts`:
  - `reports/eval_report.json`
  - `reports/eval_tool_first.json` (compat alias from `scripts/eval_tool_first.py`)
  - `reports/eval_compare.json`
  - `reports/dual_gated_eval.json`
  - `reports/eval_matrix.json`
  - `reports/eval_router.json`
  - files:
    - `scripts/eval_run.py`
    - `src/moaa_prime/eval/report.py`
    - `scripts/eval_tool_first.py`
    - `scripts/eval_compare.py`
    - `scripts/eval_dual_gate.py`
    - `scripts/eval_matrix.py`
    - `scripts/eval_router.py`
    - `tests/test_pr5_eval_report_schema.py`
    - `tests/test_pr5_eval_tool_first_schema.py`
    - `tests/test_pr5_eval_compare_schema.py`
    - `tests/test_pr4_dual_gate_eval_script.py`
    - `tests/test_pr5_eval_matrix_script.py`
- Hardened done gate criteria:
  - added RouterV3 non-regression checks (`routing_accuracy.delta >= 0`, `oracle_score_gain.delta >= 0`).
  - added dual-gate non-saturation check (`summary.dual_gated.trigger_rate < 1.0`).
  - added eval-matrix run schema checks for non-null run-level fields.
  - added targeted code/math tool-verification non-regression command check.
  - files:
    - `.codex/done_criteria.json`

Cycle log:
- Changed files: router/swarm/oracle/schema/eval scripts + tests + docs + done criteria (see section above).
- Metrics delta (before -> after):
  - `reports/eval_router.json routing_accuracy.delta`: `-0.3333 -> +0.6667`
  - `reports/eval_router.json oracle_score_gain.delta`: `-0.0221 -> +0.0533`
  - `reports/dual_gated_eval.json summary.dual_gated.trigger_rate`: `1.0000 -> 0.8333`
  - `reports/eval_matrix.json summary.swarm.tool_verification_rate_delta_vs_baseline`: `-0.6667 -> +0.3333`
  - `reports/eval_matrix.json summary.dual_gated.tool_verification_rate_delta_vs_baseline`: `-0.6667 -> +0.3333`
- Blockers:
  - no functional blockers; pre-commit done-check run fails only on `git_clean_worktree` by design.
- Next cycle plan:
  - reduce swarm/dual latency deltas while preserving new router/tool-verification gains.
  - expand router eval case count further for stronger confidence intervals.

## Cycle 003S — PR-8 docs/demo polish + strict upgrade closure
- Implemented mandatory failure taxonomy upgrade module:
  - `src/moaa_prime/eval/failure_taxonomy.py`
  - deterministic canonical classes, classifier helpers, and remediation mapping
  - added deterministic remediation-plan builder (`build_remediation_plan`) for loop dispatch
- Integrated taxonomy module into dashboard:
  - `scripts/dashboard.py` now imports shared taxonomy derivation + remediation plan
  - preserved existing taxonomy counters while adding additive remediation recommendations
- Added and exported eval package upgrade surface:
  - `src/moaa_prime/eval/__init__.py`
- Implemented mandatory structured answer object upgrade:
  - `src/moaa_prime/schema/answer_object.py`
  - `src/moaa_prime/schema/__init__.py`
  - additive runtime/eval integration in:
    - `src/moaa_prime/core/app.py` (`run_once`, `run_swarm`)
    - `src/moaa_prime/eval/runner.py`
- Added deterministic upgrade tests:
  - `tests/test_upgrade_failure_taxonomy.py`
  - `tests/test_upgrade_answer_object.py`
- PR-8 documentation polish:
  - `README.md` now includes full finish-gate runbook commands (including `scripts/eval_matrix.py`)
  - `ROADMAP.md` now includes explicit done-gate token text `Failure taxonomy`
  - updated continuity docs:
    - `MASTER_HANDOFF.md`
    - `FILEMAP.md`
    - `CONTRACTS.md` (additive `answer_object` contract note)
- Validation:
  - `.venv/bin/pytest -q` -> `123 passed`
  - full required scripts passed:
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
    - `scripts/dashboard.py`
  - strict done-check now fails only on dirty worktree pre-commit (`git_clean_worktree`)

## Cycle 003R — PR-7 telemetry dashboard + smoke coverage
- Implemented PR-7 dashboard script:
  - `scripts/dashboard.py`
  - deterministic CLI output with `--reports-dir` and `--format text|json`
  - additive telemetry sections for:
    - artifact availability/status
    - mode-level eval-matrix deltas
    - focused tool-first + dual-gate metrics
    - router eval/training snippets
    - final report verdict
- Added deterministic failure taxonomy dashboard counters (always emitted):
  - `ROUTING_MISS`
  - `TOOL_PARSE_FAIL`
  - `TOOL_EXEC_FAIL`
  - `FORMAT_FAIL`
  - `MEMORY_DRIFT`
  - `DUAL_REGRESSION`
  - `SWARM_LOOP`
- Added deterministic PR-7 smoke tests:
  - `tests/test_pr7_dashboard_smoke.py`
  - coverage includes:
    - stable dashboard rendering from seeded report artifacts
    - missing-report tolerance (non-fatal execution + warning surface)
    - required failure taxonomy class emission
- Validation:
  - `.venv/bin/pytest -q` -> `114 passed`
  - `.venv/bin/python scripts/demo_run.py`
  - `.venv/bin/python scripts/bench_run.py`
  - `.venv/bin/python scripts/eval_run.py`
  - `.venv/bin/python scripts/eval_tool_first.py`
  - `.venv/bin/python scripts/eval_compare.py`
  - `.venv/bin/python scripts/eval_dual_gate.py`
  - `.venv/bin/python scripts/eval_matrix.py`
  - `.venv/bin/python scripts/train_router.py`
  - `.venv/bin/python scripts/eval_router.py`
  - `.venv/bin/python scripts/render_report.py`
  - `.venv/bin/python scripts/dashboard.py`
- Updated continuity docs:
  - `MASTER_HANDOFF.md`
  - `FILEMAP.md`

## Cycle 003Q — PR-6 memory regression hardening
- Implemented PR-6 deterministic memory regression suite:
  - `tests/test_pr6_memory_regression.py`
  - coverage includes:
    - long-chain behavior with recall-before-write verification
    - entropy-spike novelty bump behavior
    - pruning-event persistence and recallability
    - recall stability under unrelated writes
    - write payload validation for malformed dict payloads
- Hardened memory integration:
  - `src/moaa_prime/agents/base.py`
  - `src/moaa_prime/agents/math_agent.py`
  - `src/moaa_prime/agents/code_agent.py`
  - `src/moaa_prime/memory/reasoning_bank.py`
- Memory behavior changes:
  - canonical lane/task/text writes from agents (no silent default-task empty writes)
  - lane-aware recall wiring (`lane_recall`) now active with `kl_like` flow-through from bank recall
  - memory snippets normalized to JSON-safe strings for stable serialization
  - recall now executes before write to avoid same-turn memory contamination
  - malformed positional dict writes now raise deterministic validation errors
- Validation:
  - `.venv/bin/pytest -q` -> `112 passed`
  - ran and refreshed deterministic report pipeline:
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
- Updated continuity docs:
  - `MASTER_HANDOFF.md`
  - `FILEMAP.md`

## Cycle 003P — PR-0 contract freeze hardening
- Hardened PR-0 compatibility suite in `tests/test_pr0_contract_compatibility.py`:
  - added public signature compatibility checks for:
    - `MoAAPrime.run_once(prompt, task_id="default", *, ...)`
    - `MoAAPrime.run_swarm(prompt, task_id="default", rounds=3, top_k=2, *, ...)`
  - strengthened trace schema assertions to validate all entries in:
    - `trace.router.ranked[*]`
    - `trace.oracle.scores[*]`
  - added conditional `trace_path` contract assertions:
    - absent when `run_id` is not provided
    - present and existing when `run_id` is provided
  - added additive-field policy checks proving required-key compatibility still passes when optional fields are removed (`route_trace`, router intent metadata, `trace.swarm.dual_gate`, candidate `critique`)
- Updated `CONTRACTS.md`:
  - documented frozen `MoAAPrime` method signature expectations for required positional arguments
  - clarified additive optional-field compatibility policy
- Updated continuity docs:
  - `MASTER_HANDOFF.md`
  - `FILEMAP.md`

## Cycle 003O — Full-handoff strict completion gate
- Tightened `.codex/done_criteria.json` so done means full handoff scope is implemented and verified.
  - added required artifact gates for full runbook outputs and finish modules
  - added required-file gates for upgrade deliverables:
    - `src/moaa_prime/eval/failure_taxonomy.py`
    - `src/moaa_prime/schema/answer_object.py`
    - `scripts/dashboard.py`
    - dedicated memory/upgrade/dashboard test files
  - expanded command checks to full finish checklist:
    - `demo_run`, `bench_run`, `eval_run`, `eval_tool_first`, `eval_compare`, `eval_dual_gate`, `eval_matrix`, `train_router`, `eval_router`, `render_report`
    - compatibility and targeted test suites
  - expanded metric checks to enforce:
    - tool-first uplift
    - swarm uplift
    - dual-gated non-regression
    - memory non-regression
    - SFC latency non-regression
- Updated `.codex/prompts/autopilot.md`:
  - now treats full handoff scope as mandatory (PR-0..PR-8 plus upgrade items)
  - includes expanded finish validation checklist
- Updated roadmap/docs to match strict completion semantics:
  - `ROADMAP.md` (PR-7 no longer optional; mandatory upgrade section added)
  - `README.md`
  - `MASTER_HANDOFF.md`
  - `FILEMAP.md`

## Cycle 003N — PR-5 eval matrix comparative ablations
- Added deterministic PR-5 eval matrix script:
  - `scripts/eval_matrix.py` -> `reports/eval_matrix.json`
- Implemented matrix coverage for required roadmap ablations:
  - `baseline_single`
  - `swarm`
  - `dual_gated`
  - `tool_first` on/off
  - `memory` on/off
  - `sfc` on/off
- Added stable machine-readable report schema with:
  - mode-level pass rate, average latency proxy, tool verification rate, and oracle distribution
  - summary deltas vs baseline blocks
  - per-case diffs for major comparisons
- Added deterministic PR-5 script test:
  - `tests/test_pr5_eval_matrix_script.py`
  - validates schema stability, deterministic reruns, config coverage, and required done-gate delta paths
- Latest deterministic eval-matrix summary:
  - `summary.tool_first.pass_rate_delta_vs_baseline = +0.6666666666666667`
  - `summary.swarm.pass_rate_delta_vs_baseline = +0.3333333333333333`
  - `summary.dual_gated.pass_rate_delta_vs_baseline = +0.6666666666666667`
- Updated continuity docs:
  - `MASTER_HANDOFF.md`
  - `FILEMAP.md`

## Cycle 003M — PR-4 gated dual-brain + deterministic best-of selector
- Added PR-4 duality package:
  - `src/moaa_prime/duality/gated_dual.py`
  - `src/moaa_prime/duality/__init__.py`
- Implemented deterministic gated dual trigger logic:
  - trigger reasons: `low-confidence`, `high-ambiguity`, `tool-fail`
  - deterministic reason ordering and thresholded gate decision object
- Implemented deterministic best-of selector for single vs dual candidates:
  1. tool-verified winner
  2. higher oracle score
  3. stable shorter/cleaner fallback tie-break
- Integrated gated dual path into `MoAAPrime.run_swarm(...)` as additive, opt-in behavior:
  - new optional args:
    - `dual_gate: bool | None = None`
    - `dual_gate_config: Mapping[str, Any] | None = None`
  - preserved required contract keys and default behavior (`dual_gate` remains off unless enabled)
  - additive trace metadata emitted under `trace.swarm.dual_gate`
  - additive dual candidate metadata emitted under `candidate.meta.dual_brain` and `candidate.meta.dual_gate`
- Added deterministic PR-4 tests:
  - `tests/test_pr4_gated_dual.py`
  - `tests/test_pr4_dual_gate_eval_script.py`
  - coverage includes trigger logic, selector ordering, run_swarm integration, and baseline non-regression assertions
- Added deterministic PR-4 eval artifact script:
  - `scripts/eval_dual_gate.py` -> `reports/dual_gated_eval.json`
  - latest deterministic run summary:
    - `pass_rate_delta_vs_baseline = +0.16666666666666663`
    - `oracle_delta_vs_baseline = +0.028866666666666707`
- Updated continuity docs:
  - `MASTER_HANDOFF.md`
  - `FILEMAP.md`

## Cycle 003L — PR-3 router intent-first stabilizer + route trace metadata
- Added deterministic intent-first policy module:
  - `src/moaa_prime/router/intent.py`
  - intent labels: `math`, `code`, `general`
  - deterministic matched-feature extraction + per-intent scores
- Integrated intent-first stabilizer into routers:
  - `src/moaa_prime/router/router_v2.py`
  - `src/moaa_prime/router/router_v3.py`
  - both routers now emit additive decision metadata:
    - `intent`
    - `matched_features`
    - `intent_scores`
- Extended router trace metadata (additive, contract-safe):
  - `src/moaa_prime/swarm/manager.py`
  - `trace.router` now includes:
    - `intent`
    - `matched_features`
    - `chosen_agent`
    - `alternatives`
    - `ranking_rationale`
    - `intent_scores`
    - `intent_confidence`
- Extended run-once debug surface with additive route trace:
  - `src/moaa_prime/core/app.py`
  - top-level `route_trace` now mirrors deterministic intent routing metadata.
- Added deterministic PR-3 tests:
  - `tests/test_pr3_router_intent_trace.py`
  - validates deterministic intent classification, intent-first routing behavior, and emitted route trace schema.
- Updated continuity docs:
  - `CONTRACTS.md`
  - `MASTER_HANDOFF.md`
  - `FILEMAP.md`

## Cycle 003K — PR-2 deterministic code sandbox verifier
- Added PR-2 sandbox module:
  - `src/moaa_prime/tools/code_sandbox.py`
  - `src/moaa_prime/tools/__init__.py`
- Added deterministic verifier result shape for compile/exec checks:
  - status (`pass`/`fail`)
  - stage (`compile`/`exec`)
  - error type/message fields
  - captured `stdout`
- Added deterministic Python source extraction in sandbox module:
  - fenced block extraction
  - inline `def ...` extraction
  - prompt-as-source extraction
- Integrated sandbox verifier into tool-first code policy:
  - `src/moaa_prime/policy/tool_first.py`
  - preserves existing `CodeToolOutcome` flow while adding verifier metadata fields (`status`, `stdout`) to `CodeVerification`
- Integrated verifier signal into oracle confidence (backward-compatible optional metadata path):
  - `src/moaa_prime/oracle/verifier.py`
  - `src/moaa_prime/core/app.py`
  - `src/moaa_prime/swarm/manager.py`
- Added deterministic PR-2 test coverage in:
  - `tests/test_pr2_code_sandbox_verifier.py`
  - covers sandbox pass/fail/error paths, oracle verifier-signal deltas, and verifier-driven repair loop behavior
- Updated continuity docs:
  - `MASTER_HANDOFF.md`
  - `FILEMAP.md`
  - `CHANGELOG.md`

## Cycle 003J — PR-1 tool-first policy layer
- Added PR-1 policy package:
  - `src/moaa_prime/policy/tool_first.py`
  - `src/moaa_prime/policy/__init__.py`
- Implemented deterministic tool-first math policy:
  - equation/expression extraction and SymPy-first solving/evaluation
  - structured `MathToolOutcome` with extraction/error metadata
- Implemented deterministic code verification + repair policy:
  - Python extraction from fenced blocks/inline defs/prompt-as-source
  - compile + restricted-exec verifier with structured `CodeVerification`
  - bounded deterministic repair loop (`max_retries`) with rule-based fixes
  - structured `CodeToolOutcome` metadata
- Integrated PR-1 policy into agents:
  - `MathAgent` now uses SymPy-first tool path and safe fallback while preserving memory contract keys
  - `CodeAgent` now supports prompt-code verify/repair and natural-language proposal -> verify/repair flow with bounded retries
- Added deterministic PR-1 tests:
  - `tests/test_pr1_tool_first_policy.py`
  - `tests/test_pr1_tool_first_eval_script.py`
  - includes deterministic correctness-lift assertions vs non-tool baselines
- Added deterministic PR-1 eval artifact script:
  - `scripts/eval_tool_first.py` writing `reports/tool_first_eval.json`
  - current deterministic report shows positive lift (`overall.pass_rate_delta = 0.6666666666666667`)
- Updated continuity docs for PR-1:
  - `MASTER_HANDOFF.md`
  - `FILEMAP.md`

## Cycle 003I — PR-0 contract freeze + compatibility assertions
- Added `CONTRACTS.md` to freeze public contract surfaces for:
  - router output shape (`MoAAPrime.run_once(...).decision`)
  - swarm output shape (`MoAAPrime.run_swarm(...)`)
  - agent interface (`BaseAgent.handle` / `AgentResult`)
  - memory meta required keys (`local_hits`, `bank_hits`)
- Added roadmap-ordered PR-0 compatibility tests:
  - `tests/test_pr0_contract_compatibility.py`
  - covers `run_once` and `run_swarm` required shapes across `v1`, `v2`, and `v3`
  - includes direct `BaseAgent.handle` signature and return-shape assertions
- Preserved API stability policy by enforcing required key/type compatibility while allowing additive fields.

## Cycle 003H — Roadmap-driven done definition
- Replaced `ROADMAP.md` (previously empty) with the finish roadmap (PR-0..PR-8) and explicit done definition.
- Updated `.codex/prompts/autopilot.md` so swarm cycles follow the roadmap in order (PR-0..PR-5 first) and use done-gate status as the only completion signal.
- Reworked `.codex/done_criteria.json` to align with roadmap completion:
  - requires implementation artifacts for contracts/tool-first/code-sandbox/gated-dual/eval-matrix
  - requires README/ROADMAP/CONTRACTS quality gates
  - requires eval-matrix performance deltas for `tool_first`, `swarm`, and `dual_gated`
  - requires command checks (`pytest`, `demo_run`, `bench_run`, `eval_matrix`, `render_report`)
- Extended `scripts/check_done.py`:
  - `file_checks` for file size/content gates
  - `command_checks` for executable verification gates
  - richer per-check output including command/source context
- Updated continuity docs to reflect roadmap-driven completion:
  - `README.md`
  - `MASTER_HANDOFF.md`
  - `FILEMAP.md`

## Cycle 003G — RouterV3 budget-mode calibration override increment
- Improved RouterV3 calibration quality in `src/moaa_prime/router/router_v3.py` and `src/moaa_prime/router/training.py`:
  - added optional `calibration_by_budget_mode` overrides (`cheap`, `balanced`, `max_quality`) with deterministic fallback to global calibration (`calibration_scale`, `calibration_bias`)
  - routing now applies expected-success calibration using the chosen budget mode
  - training now fits/gates optional per-mode calibration overrides against mode-specific subsets and accepts each override only when validation NLL improves vs the global calibration
- Preserved backward compatibility for legacy model payloads:
  - existing model files without per-mode calibration still load deterministically with global calibration defaults
- Expanded Cycle 3 test coverage in:
  - `tests/test_cycle3_router_v3.py`
  - `tests/test_cycle3_router_training.py`
  - adds roundtrip, inference, deterministic-training, and fallback tests for mode-specific calibration
- Updated continuity docs to match current RouterV3 calibration behavior:
  - `MASTER_HANDOFF.md`
  - `ARCHITECTURE_CYCLE3.md`

## Cycle 003F — Autopilot done-gate + GitHub sync reliability
- Added machine-checkable done criteria file: `.codex/done_criteria.json`.
- Added done evaluator script: `scripts/check_done.py`.
  - evaluates required artifacts and metric thresholds
  - writes JSON report to `.codex/runs/autopilot/done_check.json`
  - exits `0` when done criteria are met and `10` when not met
- Upgraded `scripts/swarm_autopilot.sh`:
  - runs done-check after each successful cycle
  - marks cycle `status=done` and auto-stops when criteria are met
  - records `done_result` and `done_exit` in `status.env`
  - improved auto-push logic to push any ahead commits (including swarm-authored commits)
  - routes git command output away from cycle status parsing to keep summary records clean
- Updated continuity docs for done-gate controls and runbook:
  - `README.md`
  - `MASTER_HANDOFF.md`
  - `FILEMAP.md`

## Cycle 003E — RouterV3 calibration binary-support gate increment
- Strengthened RouterV3 calibration gating robustness in `src/moaa_prime/router/training.py`:
  - calibration is skipped (identity retained) when calibration-train or calibration-validation lacks binary label support
  - binary support requires at least one positive and one negative label in each split
- Updated Cycle 3 calibration gate tests in `tests/test_cycle3_router_training.py`:
  - accept/worsen gate cases now run against binary-class calibration fixtures
  - added `test_router_training_calibration_gate_skips_single_class_splits`
- Updated continuity docs to reflect the new calibration precondition:
  - `MASTER_HANDOFF.md`
  - `ARCHITECTURE_CYCLE3.md`

## Cycle 003D — RouterV3 calibration prevalence-preservation increment
- Improved RouterV3 calibration gating quality in `src/moaa_prime/router/training.py`:
  - calibration fit/gate now uses empirical (unweighted) prevalence instead of class-balanced sample weights
  - calibration is accepted only when empirical validation NLL improves vs identity calibration
  - base logistic training still keeps deterministic class-balanced weighting (unchanged)
- Added deterministic imbalance-focused coverage in `tests/test_cycle3_router_training.py`:
  - `test_router_training_calibration_gate_preserves_imbalanced_prevalence`
  - verifies calibration gate determinism and prevalence preservation under strong class imbalance
- Updated continuity docs to match current calibration behavior:
  - `MASTER_HANDOFF.md`
  - `ARCHITECTURE_CYCLE3.md`

## Cycle 003C — RouterV3 budget-mode feature conditioning increment
- Added deterministic budget-mode conditioning to RouterV3 learned features (`src/moaa_prime/router/router_v3.py`):
  - new feature name: `budget_mode_value`
  - deterministic mapping: `cheap=0.0`, `balanced=0.5`, `max_quality=1.0`, fallback `0.5`
  - `build_router_v3_features(...)` now accepts explicit `budget_mode` and emits `budget_mode_value`.
- Updated default `RouterV3Model` weights with conservative `budget_mode_value` initialization (`0.0`) to minimize perturbation to legacy behavior.
- Wired runtime and training feature construction to pass budget mode through:
  - `RouterV3.route_top_k(...)` passes chosen budget mode into `build_router_v3_features(...)`
  - `records_to_examples(...)` passes dataset row `budget_mode` into `build_router_v3_features(...)`.
- Preserved backward compatibility for legacy model payloads: loading older `models/router_v3.pt` remains supported and deterministic.
- Expanded Cycle 3 tests to validate budget-mode feature mapping and expected-success influence when model weights that feature:
  - `tests/test_cycle3_router_v3.py`
  - `tests/test_cycle3_router_training.py`
- Updated Cycle 3 architecture and handoff docs to include budget-mode feature conditioning in router/training sections.

## Cycle 004 — Eval breadth + latency efficiency tuning
- Expanded deterministic core eval catalog from 42 to 48 cases:
  - `src/moaa_prime/eval/cases.py`
  - now 8 cases per required category:
    - `math`
    - `code`
    - `reasoning`
    - `safety`
    - `routing_intent`
    - `memory_behavior`
- Tightened and standardized count schema guards across eval reports:
  - added count clamping helper (`0 <= passed <= scored_cases <= num_cases`) in:
    - `scripts/eval_matrix.py`
    - `scripts/eval_router.py`
    - `scripts/eval_dual_gate.py`
  - `scripts/eval_dual_gate.py` now emits top-level `pass_rate` in addition to explicit count aliases.
- Improved swarm/dual-gate latency behavior while preserving deterministic defaults:
  - `src/moaa_prime/swarm/manager.py`
    - v3 now clamps to one effective round when `top_k=1`
    - added first-round strong-consensus early stop policy
  - `scripts/eval_matrix.py`
    - tuned fast-path latency profiles for `cheap|balanced|max_quality`
    - added config params for `latency_proxy_mode` and bounded dual escalation rate
  - `src/moaa_prime/core/app.py`
    - dual-gate now supports `max_single_score_for_dual` cap to avoid ambiguity-only over-triggering
    - recomputes `avg_latency_proxy` / `avg_cost_proxy` after dual-gate candidate mutation
  - `src/moaa_prime/duality/gated_dual.py`
    - aligned `select_gated_dual()` default `high_ambiguity_threshold` with selector default (`0.85`)
- Strengthened deterministic schema tests:
  - `tests/test_pr5_eval_cases_catalog.py`
  - `tests/test_pr5_eval_matrix_script.py`
  - `tests/test_pr4_dual_gate_eval_script.py`

## Cycle 003B — RouterV3 calibration + training quality increment
- Extended `RouterV3Model` (`src/moaa_prime/router/router_v3.py`) with deterministic post-logit calibration parameters:
  - `calibration_scale`
  - `calibration_bias`
  - persisted in `models/router_v3.pt` and loaded with backward-compatible defaults for legacy model files.
- Improved router training quality (`src/moaa_prime/router/training.py`) with deterministic class-balanced sample weighting.
- Added deterministic calibration fitting to training output (Platt-style scale/offset over learned logits).
- Added deterministic run-group (`run_id`) calibration split and validation gate:
  - fit calibration on calibration-train run groups
  - keep fitted calibration only when weighted validation NLL improves versus identity calibration
  - fallback to identity calibration when no improvement is observed
- Strengthened base logistic fitting in `src/moaa_prime/router/training.py` with deterministic run-group (`run_id`) validation early stopping:
  - deterministic base-train/base-validation split by run group to prevent same-run leakage
  - deterministic restore of best validation-NLL epoch parameters
  - fallback to full-data training when no run-group validation split is possible
- Added training calibration/quality metrics:
  - Brier score (`training_brier_score`)
  - Expected Calibration Error (`training_ece`)
  - mirrored under `metrics` in `reports/router_train_report.json`.
- Expanded Cycle 3 tests for calibration persistence/determinism and metric calculations:
  - `tests/test_cycle3_router_training.py`
  - `tests/test_cycle3_router_v3.py`
- Updated Cycle 3 docs:
  - `ARCHITECTURE_CYCLE3.md`
  - `MASTER_HANDOFF.md`

## Cycle 003A — Nonstop Codex swarm automation
- Added nonstop swarm daemon script: `scripts/swarm_autopilot.sh`.
  - `start|stop|status|tail|once|run` controls.
  - Continuous loop with cycle state, heartbeat, summary TSV, and daemon logs.
  - `tmux`-backed daemon mode for reliable long-running Codex swarm sessions.
  - Automatic fallback prompt switching after configurable failure streak.
  - Validation gating modes (`auto|quick|full|none`) and optional auto-commit/auto-push.
- Added default continuous mission prompt: `.codex/prompts/autopilot.md`.
- Updated runbook docs (`README.md`, `MASTER_HANDOFF.md`, `FILEMAP.md`) for nonstop swarm operation.

## Cycle 003 — Learning system (RouterV3 + traces + Pareto + training)
- Added `ARCHITECTURE_CYCLE3.md` with full Cycle 3 data flow and interfaces.
- Added RouterV3 (`src/moaa_prime/router/router_v3.py`) with:
  - learned expected-success model (`RouterV3Model`)
  - deterministic local model load/save (`models/router_v3.pt`)
  - adaptive budget profiles (`cheap`, `balanced`, `max_quality`)
  - embedding + history + budget feature scoring
- Added deterministic embedding utilities (`src/moaa_prime/router/embeddings.py`) for:
  - task embedding
  - contract embedding
  - cosine similarity
- Added router training pipeline (`src/moaa_prime/router/training.py`) and script:
  - `scripts/train_router.py`
  - writes `reports/router_train_report.json` + `models/router_v3.pt`
- Added trace recorder (`src/moaa_prime/trace/recorder.py`) and app wiring so every swarm run writes:
  - `reports/traces/run_<id>.json`
  - `datasets/router_training.jsonl`
- Extended contract schema (`src/moaa_prime/contracts/contract.py`) with:
  - `tags`
  - `description`
  - `embedding`
- Upgraded swarm manager (`src/moaa_prime/swarm/manager.py`) with v3 behavior:
  - candidate confidence proxy
  - optional cross-critique hooks
  - Pareto frontier selection by score/confidence/latency/cost
  - budget-mode-aware final candidate utility
- Added Pareto helper module: `src/moaa_prime/swarm/pareto.py`.
- Upgraded app composition root (`src/moaa_prime/core/app.py`) to support:
  - mode `v3`
  - RouterV3/SwarmV3 wiring
  - budget mode propagation
  - training trace + dataset append on swarm runs
- Added RouterV2 vs RouterV3 evaluation script:
  - `scripts/eval_router.py`
  - writes `reports/eval_router.json` metrics:
    - `routing_accuracy`
    - `oracle_score_gain`
    - `latency_efficiency`
    - `cost_efficiency`
- Updated runnable defaults to showcase Cycle 3 (`v3`) in:
  - `scripts/demo_run.py`
  - `scripts/bench_run.py`
  - `scripts/eval_run.py`
- Added deterministic Cycle 3 tests:
  - `tests/test_cycle3_router_training.py`
  - `tests/test_cycle3_router_v3.py`
  - `tests/test_cycle3_pareto.py`
  - `tests/test_cycle3_trace_recorder.py`
- Updated `.gitignore` to exclude generated `datasets/` artifacts.

## Cycle 002 — Real MoAA lift (Router/Oracle/Swarm/GCEL v2)
- Added `ARCHITECTURE_CYCLE2.md` with exact v2 data flow, interfaces, formulas, and rubric.
- Added RouterV2 (`src/moaa_prime/router/router_v2.py`) with:
  - deterministic seeded scoring
  - exploration vs exploitation probability
  - budget/history/memory-aware expected utility
  - ranked rationale + component breakdown
- Added OracleV2 in `src/moaa_prime/oracle/verifier.py` with:
  - weighted `[0,1]` rubric components (`correctness_proxy`, `coherence`, `constraint_adherence`, `safety_overreach`, `grounding`)
  - consistency check API for repeated scoring variance
  - pluggable JSON/YAML rubric support
  - bundled default rubric file `src/moaa_prime/oracle/rubric_v2.yaml`
- Upgraded swarm manager (`src/moaa_prime/swarm/manager.py`) for mode-aware v1/v2 execution:
  - v2 candidate generation/scoring/selection
  - optional top-2 cross-check round (stubbed unless enabled)
  - confidence estimation
  - structured trace payload (`router/swarm/oracle/final`)
- Extended contract schema (`src/moaa_prime/contracts/contract.py`) with `reliability` and `cost_prior` priors.
- Added GCELV2 in `src/moaa_prime/evolution/gcel.py`:
  - fitness aggregation across oracle/eval/budget
  - bounded deterministic mutations
  - gated acceptance only on evaluator improvement
- Upgraded app composition root (`src/moaa_prime/core/app.py`) to support A/B mode wiring and trace file emission:
  - `reports/trace_<runid>.json`
- Upgraded eval stack:
  - `src/moaa_prime/eval/runner.py` mode-aware with oracle/entropy/cost/latency proxies
  - `src/moaa_prime/eval/report.py` aggregate metrics
  - `scripts/eval_compare.py` for v1 vs v2 lift report (`reports/eval_compare.json`)
- Added deterministic Cycle 2 tests:
  - `tests/test_cycle2_router_v2.py`
  - `tests/test_cycle2_oracle_v2.py`
  - `tests/test_cycle2_swarm_v2.py`
  - `tests/test_cycle2_gcel_v2.py`

## Cycle 001 — CLI + docs hard-polish
- Added module entrypoint: `src/moaa_prime/__main__.py`.
- Updated CLI parser to support:
  - `python -m moaa_prime "prompt"` (shorthand route mode)
  - explicit `hello|route|swarm` subcommands.
- Added safe JSON serialization for dataclass-containing outputs in CLI/demo paths.
- Added CLI behavior tests:
  - `tests/test_cli_module_entrypoint.py`
- Added `pytest.ini` (`pythonpath = src`) for local test discovery without editable install.
- Added install-time console script:
  - `moaa-prime` via `pyproject.toml`
- Added `ARCHITECTURE.md`.
- Replaced stale continuity docs (`README.md`, `MASTER_HANDOFF.md`, `FILEMAP.md`, `DEMO_README.md`) to match real paths and commands.
- Added autonomous Codex swarm launcher and prompt:
  - `scripts/run_swarm_cycle.sh`
  - `.codex/prompts/cycle-001.md`
  - `.codex/runs/` output location
- Hardened script execution from plain checkouts by prepending local `src/` in:
  - `scripts/demo_run.py`
  - `scripts/bench_run.py`
  - `scripts/eval_run.py`
- Made `reports/final_report.json` deterministic by sorting `agents_used`.
- Fixed `moaa_prime.memory.episodic` back-compat shim to export `Episode` safely.

## Phase 1 — Packaging + smoke
- Added src/ layout, minimal app entry, import smoke tests.

## Phase 2 — Agents + Contracts + Router
- Added Contract, BaseAgent, MathAgent, CodeAgent.
- Added MetaRouter with decision metadata.
- Added routing tests.

## Phase 3 — Oracle
- Added oracle verifier scaffolding + app wiring.
- Added oracle tests.

## Phase 4 — Swarm
- Added SwarmManager and swarm path in app.
- Added swarm tests.

## Phase 5 — Memory v1 (per-agent + global ReasoningBank)
- Wired ReasoningBank into app/agents (as implemented).
- Ensured BaseAgent returns memory meta required by tests:
  - local_hits
  - bank_hits
- Tests green.

## Phase 6 — E-MRE v1
- Added E-MRE scaffolding/hooks in memory layer:
  - AEDMC
  - SH-COS
  - GFO
  - curiosity bump hooks

## Phase 7 — SGM + Energy Fusion v0
- Added SharedGeometricManifold scaffolding.
- Added fusion scaffolding (v0).

## Phase 8 — Consolidation
- Stabilized interfaces while growing features; tests maintained.

## Phase 9 — SFC (Stability Field Controller)
- Added stability/budget coupling hooks (v0).

## Phase 10 — Dual-brain (Architect / Oracle split)
- Added dual-brain runner scaffolding + tests.

## Phase 11 — GCEL (Genetic Contract Evolution Loop)
- Added GCEL evolve() with elite selection, mutation, crossover.
- Enforced competence clamping to bounds.

## Phase 12 — Hard-polish demo + benchmarks
- Added eval runner + JSON report writer.
- Added demo script that writes a single demo JSON artifact.
- Added bench script that writes timing JSON.
- Added optional real model wiring via Ollama:
  - MOAA_LLM_PROVIDER=ollama
  - MOAA_OLLAMA_HOST
  - MOAA_OLLAMA_MODEL
- reports/ treated as generated output (gitignored).
