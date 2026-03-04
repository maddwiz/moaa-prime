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
python scripts/render_report.py
```

Expected outputs:

- `reports/demo_run.json`
- `reports/bench.json`
- `reports/eval_report.json`
- `reports/final_report.json`

`reports/` is generated output and should stay untracked.

## Codex Swarm

```bash
./scripts/run_swarm_cycle.sh
./scripts/run_swarm_cycle.sh .codex/prompts/cycle-001.md
```

Artifacts are written to `.codex/runs/` as `*.log` and `*.final.txt`.

## Codex Swarm (Nonstop Autopilot)

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

Useful environment controls:
- `SWARM_AUTOPILOT_SLEEP_SECONDS=10` (delay between cycles)
- `SWARM_AUTOPILOT_VALIDATE_MODE=auto|quick|full|none`
- `SWARM_AUTOPILOT_FULL_VALIDATE_EVERY=5`
- `SWARM_AUTOPILOT_MAX_FAILURE_STREAK=3` (fallback prompt trigger)
- `SWARM_AUTOPILOT_AUTOCOMMIT=0|1`
- `SWARM_AUTOPILOT_AUTOPUSH=0|1`
