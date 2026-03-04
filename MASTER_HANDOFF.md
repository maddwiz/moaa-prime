# MASTER_HANDOFF — MoAA-Prime

Owner: Desmond  
Local path: `/Users/desmondpottle/Documents/New project/moaa-prime`

## Golden Rules

- Keep changes small, test-backed, and reversible.
- Update docs (`README.md`, `MASTER_HANDOFF.md`, `DEMO_README.md`) when command behavior changes.
- Treat `reports/`, `reports/traces/`, `datasets/`, and `models/` as generated output.

## Roadmap Status (PR-0, PR-1, PR-2, PR-3, PR-4)

- PR-0 is implemented:
  - contract freeze doc: `CONTRACTS.md`
  - compatibility test suite: `tests/test_pr0_contract_compatibility.py`
- Frozen contracts now explicitly cover:
  - router output shape (`run_once(...).decision`)
  - swarm output shape (`run_swarm(...)`)
  - agent interface (`BaseAgent.handle` / `AgentResult`)
  - memory meta required counters (`local_hits`, `bank_hits`)
- Compatibility policy:
  - required keys and required-key types are stable
  - additive fields are allowed
  - no silent contract removals/type changes

- PR-1 is implemented:
  - tool-first policy module: `src/moaa_prime/policy/tool_first.py`
  - agent integration: `src/moaa_prime/agents/math_agent.py`, `src/moaa_prime/agents/code_agent.py`
  - deterministic policy tests: `tests/test_pr1_tool_first_policy.py`
  - deterministic eval artifact script: `scripts/eval_tool_first.py` -> `reports/tool_first_eval.json`
- PR-1 behavior:
  - `MathAgent` runs SymPy-first equation/expression solving, then falls back safely.
  - `CodeAgent` runs deterministic verify/repair on prompt code when present.
  - For natural language code prompts, `CodeAgent` does proposal -> verify/repair loop with bounded retries.

- PR-2 is implemented:
  - deterministic code sandbox verifier: `src/moaa_prime/tools/code_sandbox.py`
  - verifier signal integrated into oracle confidence: `src/moaa_prime/oracle/verifier.py`
  - deterministic PR-2 verifier/repair-loop tests: `tests/test_pr2_code_sandbox_verifier.py`
- PR-2 behavior:
  - sandbox module owns deterministic Python extraction and compile/exec verification paths.
  - sandbox verify path includes compile-fail, exec-fail, and stdout-capture pass cases.
  - oracle confidence applies deterministic additive verifier deltas while preserving no-signal behavior.
  - code repair loop and `CodeAgent` metadata preserve verifier fields (`stage`, `error_type`, `line`, etc.).

- PR-3 is implemented:
  - deterministic intent-first rules: `src/moaa_prime/router/intent.py`
  - router integration: `src/moaa_prime/router/router_v2.py`, `src/moaa_prime/router/router_v3.py`
  - trace metadata integration: `src/moaa_prime/swarm/manager.py`, `src/moaa_prime/core/app.py`
  - deterministic PR-3 tests: `tests/test_pr3_router_intent_trace.py`
- PR-3 behavior:
  - router intent classifier deterministically labels prompts as `math`, `code`, or `general`.
  - routing decisions include additive intent metadata (`intent`, `matched_features`, `intent_scores`).
  - swarm `trace.router` now emits additive PR-3 trace fields:
    - `intent`
    - `matched_features`
    - `chosen_agent`
    - `alternatives`
    - `ranking_rationale`
  - `run_once(...)` now emits additive `route_trace` for debug surfaces without changing required contract keys.

- PR-4 is implemented:
  - gated dual selector module: `src/moaa_prime/duality/gated_dual.py`
  - duality package exports: `src/moaa_prime/duality/__init__.py`
  - app integration (opt-in and additive): `src/moaa_prime/core/app.py`
  - deterministic PR-4 tests:
    - `tests/test_pr4_gated_dual.py`
    - `tests/test_pr4_dual_gate_eval_script.py`
  - deterministic PR-4 eval artifact script:
    - `scripts/eval_dual_gate.py` -> `reports/dual_gated_eval.json`
- PR-4 behavior:
  - `run_swarm(...)` accepts additive kwargs:
    - `dual_gate: bool | None` (default off)
    - `dual_gate_config: Mapping[str, Any] | None`
  - trigger conditions are deterministic:
    - low confidence
    - high ambiguity
    - tool-fail
  - deterministic best-of selector rule order:
    1. tool-verified winner
    2. higher oracle score
    3. shorter/cleaner fallback tie-break
  - additive trace/debug surface:
    - `trace.swarm.dual_gate` with trigger reasons and selector outcome
    - dual candidate metadata under `candidate.meta.dual_brain` and `candidate.meta.dual_gate`

## Cycle 3 Truth (Learning Loop)

Execution modes:
- `v1`: legacy `MetaRouter` + `OracleVerifier` + legacy swarm/GCEL
- `v2`: `RouterV2` + `OracleV2` + Cycle 2 swarm/GCEL gating
- `v3`: `RouterV3` + contract embeddings + Pareto swarm + trace-learning pipeline (includes budget-mode feature conditioning)

Mode controls:
- `MoAAPrime(mode="v1"|"v2"|"v3")`
- env: `MOAA_AB_MODE=v1|v2|v3`

Architecture docs:
- `ARCHITECTURE_CYCLE2.md`
- `ARCHITECTURE_CYCLE3.md`
- `CONTRACTS.md`

## Current CLI Truth

Entrypoints:
- `python -m moaa_prime`
- `moaa-prime` (console script after install)

Supported subcommands:
- `hello`
- `route <prompt>`
- `swarm <prompt>`

Shorthand behavior:
- if first arg is not a known subcommand, it is treated as `route`

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install pytest pyyaml
python -m pip install -e . --no-deps
```

## Required Runbook (Cycle 3)

```bash
.venv/bin/pytest -q
.venv/bin/python scripts/demo_run.py
.venv/bin/python scripts/bench_run.py
.venv/bin/python scripts/eval_run.py
.venv/bin/python scripts/eval_tool_first.py
.venv/bin/python scripts/eval_compare.py
.venv/bin/python scripts/eval_dual_gate.py
.venv/bin/python scripts/train_router.py
.venv/bin/python scripts/eval_router.py
```

PR-0 compatibility smoke:

```bash
.venv/bin/pytest -q tests/test_pr0_contract_compatibility.py
```

PR-3 intent trace smoke:

```bash
.venv/bin/pytest -q tests/test_pr3_router_intent_trace.py
```

## Nonstop Codex Swarm Runbook

Start continuous swarm daemon:

```bash
./scripts/swarm_autopilot.sh start
```

Inspect current state:

```bash
./scripts/swarm_autopilot.sh status
./scripts/swarm_autopilot.sh tail
```

Stop daemon:

```bash
./scripts/swarm_autopilot.sh stop
```

Autopilot artifacts:
- `.codex/runs/autopilot/daemon.log`
- `.codex/runs/autopilot/status.env`
- `.codex/runs/autopilot/cycles.tsv`
- `.codex/runs/autopilot/active_prompt.md`
- `.codex/runs/autopilot/done_check.json`

Done gate:
- criteria file: `.codex/done_criteria.json`
- evaluator script: `scripts/check_done.py`
- behavior: each successful cycle evaluates done criteria; if met, status becomes `done` and daemon exits.
- roadmap source-of-truth: `ROADMAP.md` (PR-0 through PR-8)
- current done gate requires PR-0..PR-5 implementation artifacts plus eval-matrix performance deltas and runbook command checks.

Primary artifacts:
- `reports/demo_run.json`
- `reports/bench.json`
- `reports/eval_report.json`
- `reports/tool_first_eval.json`
- `reports/dual_gated_eval.json`
- `reports/eval_matrix.json`
- `reports/eval_compare.json`
- `reports/router_train_report.json`
- `reports/eval_router.json`
- `reports/traces/run_<id>.json`
- `datasets/router_training.jsonl`
- `models/router_v3.pt`

## Learning Pipeline

Every swarm run appends a training example:
- trace file: `reports/traces/run_<id>.json`
- dataset append: `datasets/router_training.jsonl`

Router training script:
- `scripts/train_router.py`
- reads traces + dataset and writes `models/router_v3.pt`
- conditions learned expected-success features on normalized budget mode (`budget_mode_value`: `cheap=0.0`, `balanced=0.5`, `max_quality=1.0`, fallback `0.5`)
- uses deterministic class-balanced weighting during logistic fitting
- uses deterministic run-group (`run_id`) train/validation split for base logistic fitting with validation-NLL early stopping
- restores the best validation-NLL base-model epoch deterministically
- falls back to full-data base training when run-group validation cannot be formed
- splits calibration data deterministically by `run_id` group into calibration-train/calibration-validation
- requires both calibration splits to contain positive and negative labels; otherwise skips calibration and keeps baseline calibration
- fits deterministic global post-logit calibration (`calibration_scale`, `calibration_bias`) on calibration-train using empirical (unweighted) prevalence
- accepts global calibration only when it improves empirical (unweighted) validation NLL vs identity on calibration-validation
- fits optional deterministic per-budget-mode calibration overrides (`calibration_by_budget_mode`) for `cheap|balanced|max_quality` on mode subsets
- accepts each mode override only when mode-specific validation NLL improves vs global calibration; otherwise that mode falls back to global calibration
- writes `reports/router_train_report.json` with:
  - `training_accuracy`
  - `training_brier_score`
  - `training_ece`
  - global calibration parameters
  - accepted per-budget-mode calibration overrides (when present)

Router evaluation script:
- `scripts/eval_router.py`
- compares `v2` vs `v3` with:
  - `routing_accuracy`
  - `oracle_score_gain`
  - `latency_efficiency`
  - `cost_efficiency`

## Environment Variables

LLM/provider wiring:
- `MOAA_LLM_PROVIDER` (`stub` default; `ollama` supported)
- `MOAA_OLLAMA_HOST` (`http://127.0.0.1:11434` default)
- `MOAA_OLLAMA_MODEL` (`llama3.1:8b-instruct` default)

Mode controls:
- `MOAA_AB_MODE=v1|v2|v3`
- `MOAA_DEMO_MODE=v1|v2|v3` (default script mode now `v3`)
- `MOAA_BENCH_MODE=v1|v2|v3` (default script mode now `v3`)
- `MOAA_EVAL_MODE=v1|v2|v3` (default script mode now `v3`)
- `MOAA_DUAL_GATE=0|1` (optional default for dual-gated swarm selection)

Router v3 / learning controls:
- `MOAA_BUDGET_MODE=cheap|balanced|max_quality`
- `MOAA_ROUTER_V3_MODEL` (default `models/router_v3.pt`)
- `MOAA_TRACE_DIR` (default `reports/traces`)
- `MOAA_ROUTER_DATASET` (default `datasets/router_training.jsonl`)
- `MOAA_ROUTER_TRAIN_SEED`
- `MOAA_ROUTER_EVAL_SEED`

Optional seeds:
- `MOAA_DEMO_SEED`
- `MOAA_BENCH_SEED`
- `MOAA_EVAL_SEED`
- `MOAA_EVAL_COMPARE_SEED`

Swarm autopilot controls:
- `SWARM_AUTOPILOT_SLEEP_SECONDS`
- `SWARM_AUTOPILOT_FULL_VALIDATE_EVERY`
- `SWARM_AUTOPILOT_MAX_FAILURE_STREAK`
- `SWARM_AUTOPILOT_VALIDATE_MODE=auto|quick|full|none`
- `SWARM_AUTOPILOT_DAEMON_MODE=auto|tmux|nohup`
- `SWARM_AUTOPILOT_TMUX_SESSION`
- `SWARM_AUTOPILOT_AUTOCOMMIT=0|1`
- `SWARM_AUTOPILOT_AUTOPUSH=0|1`
- `SWARM_AUTOPILOT_DONE_CHECK_ENABLED=0|1`
- `SWARM_AUTOPILOT_DONE_CHECK_SCRIPT`
- `SWARM_AUTOPILOT_DONE_CRITERIA`
- `SWARM_AUTOPILOT_DONE_REPORT`

Ollama example:

```bash
export MOAA_LLM_PROVIDER=ollama
export MOAA_OLLAMA_HOST="http://127.0.0.1:11434"
export MOAA_OLLAMA_MODEL="llama3.1:8b-instruct"
```
