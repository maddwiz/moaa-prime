# FILEMAP — MoAA-Prime

This maps the repo so a new context window can re-sync quickly.

## Root

- `README.md`: user-facing quickstart and CLI usage
- `MASTER_HANDOFF.md`: living continuity doc
- `ARCHITECTURE.md`: baseline architecture/contract map
- `ARCHITECTURE_CYCLE2.md`: Cycle 2 router/oracle/swarm/gcel v2 design
- `FILEMAP.md`: this file
- `CHANGELOG.md`: phase and cycle history
- `DEMO_README.md`: demo/bench/eval artifact runbook
- `pyproject.toml`: package metadata and entry points
- `pytest.ini`: test path config (`pythonpath = src`)
- `scripts/`: runnable demo + benchmark + eval scripts
- `src/moaa_prime/`: implementation
- `tests/`: test suite

## Real Entrypoints

- `pyproject.toml` `[project.scripts]`: `moaa-prime = moaa_prime.cli.main:main`
- `src/moaa_prime/__main__.py`: module entrypoint for `python -m moaa_prime ...`
- `src/moaa_prime/cli/main.py`: canonical CLI parser/dispatch
- `src/moaa_prime/core/app.py`: `MoAAPrime` runtime façade

## Major Modules

- `src/moaa_prime/contracts/contract.py`: contract priors (`competence`, `reliability`, `cost_prior`)
- `src/moaa_prime/router/meta_router.py`: v1 router
- `src/moaa_prime/router/router_v2.py`: RouterV2 scoring + exploration
- `src/moaa_prime/oracle/verifier.py`: v1 oracle + OracleV2 rubric scoring
- `src/moaa_prime/oracle/rubric_v2.yaml`: default OracleV2 rubric config
- `src/moaa_prime/swarm/manager.py`: v1/v2 swarm, confidence, structured trace
- `src/moaa_prime/evolution/gcel.py`: GCEL v1 + GCELV2 gating outcome
- `src/moaa_prime/eval/runner.py`: mode-aware eval runner with proxy metrics
- `src/moaa_prime/eval/report.py`: eval report writer with aggregate metrics
- `src/moaa_prime/llm/factory.py`: stub/ollama model provider selection

## Scripts

- `scripts/demo_run.py`: deterministic demo run, writes `reports/demo_run.json` and `trace_demo_<mode>.json`
- `scripts/bench_run.py`: benchmark run, writes `reports/bench.json`
- `scripts/eval_run.py`: writes `reports/eval_report.json`
- `scripts/eval_compare.py`: v1-v2 lift compare, writes `reports/eval_compare.json`
- `scripts/render_report.py`: rolls up demo/bench/eval outputs into `reports/final_report.json`

## Reports

Generated outputs in `reports/`:
- `demo_run.json`
- `bench.json`
- `eval_report.json`
- `eval_compare.json`
- `trace_<runid>.json` (router/swarm/oracle/final sections)

## Tests

Existing phase tests remain in `tests/test_phase*.py` plus CLI/import tests.

Cycle 2 tests:
- `tests/test_cycle2_router_v2.py`
- `tests/test_cycle2_oracle_v2.py`
- `tests/test_cycle2_swarm_v2.py`
- `tests/test_cycle2_gcel_v2.py`

## A/B Contract

A/B mode selection:
- `MoAAPrime(mode="v1"|"v2")`
- `MOAA_AB_MODE=v1|v2`

Evaluation compare command:
- `.venv/bin/python scripts/eval_compare.py`
