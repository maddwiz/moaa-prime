# MASTER_HANDOFF — MoAA-Prime

Owner: Desmond  
Local path: `/Users/desmondpottle/Documents/New project/moaa-prime`

## Golden Rules

- Keep changes small, test-backed, and reversible.
- Update docs (`README.md`, `MASTER_HANDOFF.md`, `DEMO_README.md`) when command behavior changes.
- Treat `reports/`, `reports/traces/`, `datasets/`, and `models/` as generated output.

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
.venv/bin/python scripts/eval_compare.py
.venv/bin/python scripts/train_router.py
.venv/bin/python scripts/eval_router.py
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

Primary artifacts:
- `reports/demo_run.json`
- `reports/bench.json`
- `reports/eval_report.json`
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
- requires both calibration splits to contain positive and negative labels; otherwise skips calibration and keeps identity
- fits deterministic post-logit calibration (`calibration_scale`, `calibration_bias`) on calibration-train using empirical (unweighted) prevalence
- accepts calibration only when it improves empirical (unweighted) validation NLL vs identity on calibration-validation
- writes `reports/router_train_report.json` with:
  - `training_accuracy`
  - `training_brier_score`
  - `training_ece`
  - calibration parameters

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

Ollama example:

```bash
export MOAA_LLM_PROVIDER=ollama
export MOAA_OLLAMA_HOST="http://127.0.0.1:11434"
export MOAA_OLLAMA_MODEL="llama3.1:8b-instruct"
```
