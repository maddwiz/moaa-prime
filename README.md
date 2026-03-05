# MoAA-Prime

MoAA-Prime is a Mixture of Adaptive Agents prototype with contract-based routing, oracle scoring, swarm deliberation, memory hooks, and optional Ollama-backed LLM calls.

## Quickstart

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e .
```

## Commands

Check CLI surface:

```bash
python -m moaa_prime --help
```

Supported commands:

```bash
python -m moaa_prime hello
python -m moaa_prime "Solve: 2x + 3 = 7. Return only x."   # shorthand = route
python -m moaa_prime route "Write Python: function add(a,b) returns a+b"
python -m moaa_prime swarm "Explain why 1/0 is undefined."
```

Console script (after install):

```bash
moaa-prime route "2+2?"
```

Run tests:

```bash
python -m pytest -q
```

## Environment Variables

| Variable | Default | Notes |
| --- | --- | --- |
| `MOAA_LLM_PROVIDER` | `stub` | `stub` or `ollama` |
| `MOAA_OLLAMA_HOST` | `http://127.0.0.1:11434` | Used when provider is `ollama` |
| `MOAA_OLLAMA_MODEL` | `llama3.1:8b-instruct` | Used when provider is `ollama` |
| `MOAA_OLLAMA_TIMEOUT_SEC` | `30` | Request timeout for Ollama calls |
| `MOAA_OLLAMA_MAX_RETRIES` | `2` | Retry attempts for transient Ollama failures |
| `MOAA_OLLAMA_RETRY_BACKOFF_SEC` | `0.25` | Exponential retry backoff base |

Example (Ollama):

```bash
export MOAA_LLM_PROVIDER=ollama
export MOAA_OLLAMA_HOST="http://127.0.0.1:11434"
export MOAA_OLLAMA_MODEL="llama3.1:8b-instruct"
```

## Demo Bundle

Run in this order:

```bash
python scripts/demo_run.py
python scripts/bench_run.py
python scripts/eval_run.py
python scripts/eval_tool_first.py
python scripts/eval_compare.py
python scripts/eval_dual_gate.py
python scripts/eval_matrix.py
python scripts/train_router.py
python scripts/eval_router.py
python scripts/preflight_prod.py --output reports/preflight_prod.json
python scripts/load_smoke.py --output reports/load_smoke.json --iters 50
python scripts/render_report.py
python scripts/dashboard.py
```

Expected outputs:

- `reports/demo_run.json`
- `reports/bench.json`
- `reports/eval_report.json`
- `reports/tool_first_eval.json`
- `reports/eval_tool_first.json`
- `reports/eval_compare.json`
- `reports/dual_gated_eval.json`
- `reports/eval_matrix.json`
- `reports/router_train_report.json`
- `reports/eval_router.json`
- `reports/preflight_prod.json`
- `reports/load_smoke.json`
- `reports/final_report.json`

Schema notes:
- `reports/eval_report.json`, `reports/eval_tool_first.json`, `reports/eval_compare.json`, `reports/dual_gated_eval.json`, `reports/eval_matrix.json`, and `reports/eval_router.json` all emit `schema_version: "1.1"` and include stable top-level `summary` + numeric `counts`.
- `scripts/eval_tool_first.py` writes both `reports/tool_first_eval.json` and compatibility alias `reports/eval_tool_first.json`.

`reports/` is generated output and should stay untracked.

## Codex Swarm

```bash
./scripts/run_swarm_cycle.sh
./scripts/run_swarm_cycle.sh .codex/prompts/cycle-001.md
```

Artifacts are written to `.codex/runs/` as `*.log` and `*.final.txt`.

## Codex Swarm (Nonstop Autopilot)

Roadmap source-of-truth:
- `ROADMAP.md` (PR-0 .. PR-8, done definition)

Start a continuous swarm loop (background daemon):

```bash
./scripts/swarm_autopilot.sh start
```

Use a specific prompt file:

```bash
./scripts/swarm_autopilot.sh start .codex/prompts/autopilot.md .codex/prompts/cycle-003-direct.md
```

Check status and recent cycle summaries:

```bash
./scripts/swarm_autopilot.sh status
```

Tail daemon logs:

```bash
./scripts/swarm_autopilot.sh tail
```

Stop the daemon:

```bash
./scripts/swarm_autopilot.sh stop
```

Autopilot state is stored in `.codex/runs/autopilot/`:
- `daemon.log`
- `status.env`
- `cycles.tsv`
- `active_prompt.md`
- `done_check.json`

Useful environment controls:
- `SWARM_AUTOPILOT_SLEEP_SECONDS=10` (delay between cycles)
- `SWARM_AUTOPILOT_VALIDATE_MODE=auto|quick|full|none`
- `SWARM_AUTOPILOT_FULL_VALIDATE_EVERY=5`
- `SWARM_AUTOPILOT_MAX_FAILURE_STREAK=3` (fallback prompt trigger)
- `SWARM_AUTOPILOT_DAEMON_MODE=auto|tmux|nohup` (`auto` prefers `tmux`)
- `SWARM_AUTOPILOT_TMUX_SESSION=moaa-prime-swarm-autopilot`
- `SWARM_AUTOPILOT_AUTOCOMMIT=0|1`
- `SWARM_AUTOPILOT_AUTOPUSH=0|1`
- `SWARM_AUTOPILOT_DONE_CHECK_ENABLED=0|1`
- `SWARM_AUTOPILOT_DONE_CHECK_SCRIPT=scripts/check_done.py`
- `SWARM_AUTOPILOT_DONE_CRITERIA=.codex/done_criteria.json`
- `SWARM_AUTOPILOT_DONE_REPORT=.codex/runs/autopilot/done_check.json`

Example with explicit daemon settings:

```bash
SWARM_AUTOPILOT_AUTOCOMMIT=1 SWARM_AUTOPILOT_AUTOPUSH=1 SWARM_AUTOPILOT_VALIDATE_MODE=quick ./scripts/swarm_autopilot.sh start
```

Definition of done:
- Criteria live in `.codex/done_criteria.json`.
- On each successful cycle, autopilot runs `scripts/check_done.py`.
- Criteria include full-handoff scope (roadmap PR-0..PR-8 + mandatory upgrade items).
- When criteria are met, cycle status becomes `done` and the loop exits automatically.
- Hardened gate includes RouterV3 non-regression (`routing_accuracy.delta >= 0`, `oracle_score_gain.delta >= 0`), dual-gate saturation guard (`trigger_rate < 1.0`), and eval-matrix run-level schema checks.

Run done-check manually:

```bash
python3 scripts/check_done.py --criteria .codex/done_criteria.json --report .codex/runs/autopilot/done_check.json
```

## Production Runbook

Production operations docs:
- `PRODUCTION_READINESS.md`
- `RUNBOOK_PRODUCTION.md`

Production readiness command sequence:

```bash
pytest -q
python scripts/eval_matrix.py
python scripts/eval_router.py
python scripts/eval_dual_gate.py
python scripts/preflight_prod.py --output reports/preflight_prod.json
python scripts/load_smoke.py --output reports/load_smoke.json --iters 50
python scripts/check_done.py --criteria .codex/done_criteria.production.json
```

## Known Limits

- RouterV3 still trains on a compact deterministic dataset; broad generalization requires larger and more diverse traces.
- Dual-gate still uses heuristic ambiguity/constraint signals; future work should learn trigger policy from held-out regressions.
- Stub-provider defaults are deterministic and contract-safe, but they are not representative of production model quality.
