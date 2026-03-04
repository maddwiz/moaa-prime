# MASTER_HANDOFF — MoAA-Prime

Owner: Desmond  
Local path: `/Users/desmondpottle/Documents/New project/moaa-prime`

## Golden Rules

- Keep changes small, test-backed, and reversible.
- Update docs (`README.md`, `MASTER_HANDOFF.md`, `DEMO_README.md`) when command behavior changes.
- Treat `reports/` as generated output.

## Current CLI Truth

Entrypoints:

- `python -m moaa_prime`
- `moaa-prime` (console script after `pip install -e .`)

Supported subcommands:

- `hello`
- `route <prompt>`
- `swarm <prompt>`

Shorthand behavior:

- If first arg is not a known subcommand, it is treated as `route`.
- Example: `python -m moaa_prime "Solve: 2x + 3 = 7. Return only x."`

Help:

```bash
python -m moaa_prime --help
```

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e .
```

## Runbook

Test suite:

```bash
python -m pytest -q
```

CLI smoke:

```bash
python -m moaa_prime hello
python -m moaa_prime route "Write Python: function add(a,b) returns a+b"
python -m moaa_prime swarm "Explain why 1/0 is undefined."
```

## Demo Bundle

Run in order:

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

## Environment Variables

- `MOAA_LLM_PROVIDER` (`stub` by default; `ollama` supported)
- `MOAA_OLLAMA_HOST` (`http://127.0.0.1:11434` default)
- `MOAA_OLLAMA_MODEL` (`llama3.1:8b-instruct` default)

Ollama example:

```bash
export MOAA_LLM_PROVIDER=ollama
export MOAA_OLLAMA_HOST="http://127.0.0.1:11434"
export MOAA_OLLAMA_MODEL="llama3.1:8b-instruct"
```

## Codex Swarm (Optional)

- Launcher: `./scripts/run_swarm_cycle.sh`
- Default prompt: `.codex/prompts/cycle-001.md`
- Optional prompt arg: `./scripts/run_swarm_cycle.sh <prompt-file>`
- Run artifacts: `.codex/runs/*.log`, `.codex/runs/*.final.txt`
