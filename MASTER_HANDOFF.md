# MASTER_HANDOFF — MoAA-Prime

Owner: Desmond  
Local path: `/Users/desmondpottle/Documents/New project/moaa-prime`

## Golden Rules

- Keep changes small, test-backed, and reversible.
- Update docs (`README.md`, `MASTER_HANDOFF.md`, `DEMO_README.md`) when command behavior changes.
- Treat `reports/` as generated output.

## Cycle 2 Truth (A/B + Lift)

A/B execution modes:
- `v1`: legacy `MetaRouter` + `OracleVerifier` + legacy swarm/GCEL
- `v2`: `RouterV2` + `OracleV2` + Swarm trace/confidence + `GCELV2` gating

Mode controls:
- `MoAAPrime(mode="v1"|"v2")`
- env config: `MOAA_AB_MODE=v1|v2`

Cycle 2 architecture doc:
- `ARCHITECTURE_CYCLE2.md`

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

## Required Runbook (Cycle 2)

```bash
.venv/bin/pytest -q
.venv/bin/python scripts/demo_run.py
.venv/bin/python scripts/bench_run.py
.venv/bin/python scripts/eval_run.py
.venv/bin/python scripts/eval_compare.py
```

Primary artifacts:
- `reports/demo_run.json`
- `reports/bench.json`
- `reports/eval_report.json`
- `reports/eval_compare.json`
- `reports/trace_demo_v2.json`
- `reports/trace_compare_v1_11.json`
- `reports/trace_compare_v2_11.json`

## Eval Compare Metrics

`reports/eval_compare.json` includes:
- `avg_oracle_score` (v1/v2/delta)
- `win_rate_v2_over_v1`
- `routing_entropy` (v1/v2/delta)
- `avg_cost_proxy` (v1/v2/delta)
- `avg_latency_proxy` (v1/v2/delta)

## Environment Variables

LLM/provider wiring (unchanged):
- `MOAA_LLM_PROVIDER` (`stub` default; `ollama` supported)
- `MOAA_OLLAMA_HOST` (`http://127.0.0.1:11434` default)
- `MOAA_OLLAMA_MODEL` (`llama3.1:8b-instruct` default)

Cycle 2 mode controls:
- `MOAA_AB_MODE=v1|v2`
- `MOAA_DEMO_MODE=v1|v2`
- `MOAA_BENCH_MODE=v1|v2`
- `MOAA_EVAL_MODE=v1|v2`

Optional seeds:
- `MOAA_DEMO_SEED`
- `MOAA_BENCH_SEED`
- `MOAA_EVAL_SEED`
- `MOAA_EVAL_COMPARE_SEED`

Ollama example:

```bash
export MOAA_LLM_PROVIDER=ollama
export MOAA_OLLAMA_HOST="http://127.0.0.1:11434"
export MOAA_OLLAMA_MODEL="llama3.1:8b-instruct"
```
