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
- `.codex/agents/*.toml`: role-specific multi-agent configs
- `.codex/prompts/cycle-001.md`: autonomous cycle mission prompt
- `.codex/runs/`: generated swarm logs and final messages
- `scripts/`: runnable demo + benchmark + eval scripts
- `src/moaa_prime/`: implementation
- `tests/`: test suite

## Real entrypoints

- `pyproject.toml` `[project.scripts]`: installs `moaa-prime = moaa_prime.cli.main:main`
- `src/moaa_prime/__main__.py`: module entrypoint for `python -m moaa_prime ...`
- `src/moaa_prime/cli/main.py`: canonical CLI parser/dispatch (`hello`, `route`, `swarm`)
- `src/moaa_prime/cli/phase9_stable_cmd.py`: optional Phase 9 SFC-gated swarm CLI
- `src/moaa_prime/core/app.py`: `MoAAPrime` runtime façade used by CLI/scripts/tests

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
- `scripts/run_swarm_cycle.sh`: non-interactive Codex swarm launcher

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

## Proposed CLI Contract

### Scope

This section defines the CLI behavior that callers can rely on.  
Invocation forms below are exact for the current parser in `src/moaa_prime/cli/main.py`.

### Canonical command forms

- `moaa-prime hello`
- `moaa-prime route "<prompt>"`
- `moaa-prime swarm "<prompt>"`
- `moaa-prime "<prompt>"` (shorthand for `route`)

Equivalent module forms:

- `python -m moaa_prime hello`
- `python -m moaa_prime route "<prompt>"`
- `python -m moaa_prime swarm "<prompt>"`
- `python -m moaa_prime "<prompt>"`

Repo-local (without install) form:

- `PYTHONPATH=src python3 -m moaa_prime ...`

### Expected behavior

- `hello`: prints plain text greeting (`moaa-prime says hello`), exits `0`.
- `route` and shorthand prompt:
  - print JSON object with top-level keys `decision`, `result`, `oracle`
  - exit `0` on success
- `swarm`:
  - prints JSON object with top-level keys `best`, `candidates`
  - `best` is selected by max oracle score
  - exit `0` on success
- `--help` / `-h`: argparse help text, exit `0`.
- parser errors (no command, missing prompt, unknown extra args on known subcommands): argparse usage to stderr, exit `2`.

### Optional Phase 9 stable CLI (non-canonical)

- invocation: `python -m moaa_prime.cli.phase9_stable_cmd "<prompt>"`
- expected JSON keys: `best`, `candidates`, `stopped_early`, `sfc_value`, `meta`
- empty prompt: prints usage and exits `2`
