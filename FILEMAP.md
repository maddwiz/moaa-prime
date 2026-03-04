# FILEMAP — MoAA-Prime

This maps the repo so a new context window can re-sync quickly.

## Root

- `README.md`: user-facing quickstart and CLI usage
- `MASTER_HANDOFF.md`: living continuity doc
- `ARCHITECTURE.md`: architecture and contract map
- `FILEMAP.md`: this file
- `CHANGELOG.md`: phase and cycle history
- `DEMO_README.md`: demo/bench/eval artifact runbook
- `pyproject.toml`: package metadata and entry points
- `pytest.ini`: test path config (`pythonpath = src`)
- `.codex/config.toml`: project multi-agent defaults
- `.codex/agents/*.toml`: role-specific multi-agent prompts
- `scripts/`: runnable demo + benchmark + eval scripts
- `src/moaa_prime/`: implementation
- `tests/`: test suite

## Canonical entrypoints

- `src/moaa_prime/__main__.py`: module entrypoint for `python -m moaa_prime ...`
- `src/moaa_prime/cli/main.py`: CLI parser and command handlers
- `src/moaa_prime/core/app.py`: `MoAAPrime` façade

## Major modules

- `src/moaa_prime/contracts/`: contract model
- `src/moaa_prime/agents/`: base + specialist agents
- `src/moaa_prime/router/`: routing decisions
- `src/moaa_prime/oracle/`: verifier scoring
- `src/moaa_prime/swarm/`: swarm manager and dual-brain runner
- `src/moaa_prime/memory/`: episodic lane + ReasoningBank + E-MRE hooks
- `src/moaa_prime/sgm/`: shared geometric manifold scaffolding
- `src/moaa_prime/fusion/`: fusion scaffolding
- `src/moaa_prime/sfc/`: stability field controller
- `src/moaa_prime/brains/`: architect/oracle brain stubs
- `src/moaa_prime/evolution/`: GCEL evolution loop
- `src/moaa_prime/eval/`: eval runner and report writer
- `src/moaa_prime/llm/`: stub/ollama client factory
- `src/moaa_prime/util/`: small helpers

## Scripts

- `scripts/demo_run.py`: writes `reports/demo_run.json`
- `scripts/bench_run.py`: writes `reports/bench.json`
- `scripts/eval_run.py`: writes `reports/eval_report.json`
- `scripts/render_report.py`: writes `reports/final_report.json`

## Tests

- `tests/test_phase1_smoke.py`
- `tests/test_phase2_router.py`
- `tests/test_phase3_oracle.py`
- `tests/test_phase4_swarm.py`
- `tests/test_phase5_memory.py`
- `tests/test_phase6_emre.py`
- `tests/test_phase7_sgm.py`
- `tests/test_phase7_energy_fusion.py`
- `tests/test_phase8_swarm_fusion.py`
- `tests/test_phase9_sfc.py`
- `tests/test_phase9_cli_stable_cmd.py`
- `tests/test_phase9_swarm_sfc_gate.py`
- `tests/test_phase10_dual_brain.py`
- `tests/test_phase11_gcel.py`
- `tests/test_phase12_eval_smoke.py`
- `tests/test_cli_module_entrypoint.py`
