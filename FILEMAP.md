# FILEMAP — MoAA-Prime

This maps the repo so a new context window can re-sync quickly.

## Root

- `README.md`: user-facing quickstart and CLI usage
- `MASTER_HANDOFF.md`: living continuity doc
- `ARCHITECTURE.md`: baseline architecture/contract map
- `ARCHITECTURE_CYCLE2.md`: Cycle 2 router/oracle/swarm/gcel v2 design
- `ARCHITECTURE_CYCLE3.md`: Cycle 3 learning architecture (router training + pareto + traces)
- `FILEMAP.md`: this file
- `CHANGELOG.md`: phase and cycle history
- `ROADMAP.md`: execution roadmap (PR-0..PR-8) and done definition
- `CONTRACTS.md`: frozen API/interface contract doc (PR-0)
- `DEMO_README.md`: demo/bench/eval artifact runbook
- `pyproject.toml`: package metadata and entry points
- `pytest.ini`: test path config (`pythonpath = src`)
- `.codex/prompts/autopilot.md`: default continuous swarm mission prompt
- `.codex/done_criteria.json`: machine-checkable done criteria for swarm auto-stop
- `scripts/`: runnable demo + benchmark + eval + train scripts
- `src/moaa_prime/`: implementation
- `tests/`: test suite

## Real Entrypoints

- `pyproject.toml` `[project.scripts]`: `moaa-prime = moaa_prime.cli.main:main`
- `src/moaa_prime/__main__.py`: module entrypoint for `python -m moaa_prime ...`
- `src/moaa_prime/cli/main.py`: canonical CLI parser/dispatch
- `src/moaa_prime/core/app.py`: `MoAAPrime` runtime façade (`v1`/`v2`/`v3`)

## Major Modules

- `src/moaa_prime/contracts/contract.py`: contract priors + Cycle 3 semantic fields (`tags`, `description`, `embedding`)
- `src/moaa_prime/router/meta_router.py`: v1 router
- `src/moaa_prime/router/router_v2.py`: RouterV2 scoring + exploration
- `src/moaa_prime/router/router_v3.py`: learned RouterV3 + budget profiles + model load/save
- `src/moaa_prime/router/training.py`: trace -> feature -> model training pipeline
- `src/moaa_prime/router/embeddings.py`: deterministic text/contract embedding helpers
- `src/moaa_prime/oracle/verifier.py`: v1 oracle + OracleV2 rubric scoring
- `src/moaa_prime/oracle/rubric_v2.yaml`: default OracleV2 rubric config
- `src/moaa_prime/swarm/manager.py`: v1/v2/v3 swarm, cross-critique hooks, Pareto selection
- `src/moaa_prime/swarm/pareto.py`: Pareto frontier helper
- `src/moaa_prime/evolution/gcel.py`: GCEL v1 + GCELV2 gated evolution
- `src/moaa_prime/trace/recorder.py`: trace files + router dataset appends
- `src/moaa_prime/eval/runner.py`: mode-aware eval runner with proxy metrics
- `src/moaa_prime/eval/report.py`: eval report writer with aggregate metrics
- `src/moaa_prime/llm/factory.py`: stub/ollama model provider selection

## Scripts

- `scripts/demo_run.py`: deterministic demo run (default mode `v3`)
- `scripts/bench_run.py`: benchmark run (default mode `v3`)
- `scripts/eval_run.py`: eval report run (default mode `v3`)
- `scripts/eval_compare.py`: v1-v2 compare report (`reports/eval_compare.json`)
- `scripts/train_router.py`: trains RouterV3 from traces (`models/router_v3.pt`)
- `scripts/eval_router.py`: compares RouterV2 vs RouterV3 (`reports/eval_router.json`)
- `scripts/render_report.py`: rolls up demo/bench/eval outputs into `reports/final_report.json`
- `scripts/check_done.py`: evaluates done criteria and writes done-check report
- `scripts/run_swarm_cycle.sh`: single swarm cycle launcher with prompt input
- `scripts/swarm_autopilot.sh`: nonstop swarm daemon (start/stop/status/tail)

## Generated Artifacts

- `reports/demo_run.json`
- `reports/bench.json`
- `reports/eval_report.json`
- `reports/eval_compare.json`
- `reports/router_train_report.json`
- `reports/eval_router.json`
- `reports/trace_<runid>.json`
- `reports/traces/run_<runid>.json`
- `datasets/router_training.jsonl`
- `models/router_v3.pt`

## Tests

Existing phase tests remain in `tests/test_phase*.py` plus CLI/import tests.

Roadmap PR-0 compatibility tests:
- `tests/test_pr0_contract_compatibility.py`

Cycle 2 tests:
- `tests/test_cycle2_router_v2.py`
- `tests/test_cycle2_oracle_v2.py`
- `tests/test_cycle2_swarm_v2.py`
- `tests/test_cycle2_gcel_v2.py`

Cycle 3 tests:
- `tests/test_cycle3_router_training.py`
- `tests/test_cycle3_router_v3.py`
- `tests/test_cycle3_pareto.py`
- `tests/test_cycle3_trace_recorder.py`

## Mode Contract

Mode selection:
- `MoAAPrime(mode="v1"|"v2"|"v3")`
- `MOAA_AB_MODE=v1|v2|v3`

Router training and eval commands:
- `.venv/bin/python scripts/train_router.py`
- `.venv/bin/python scripts/eval_router.py`
