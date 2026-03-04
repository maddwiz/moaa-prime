# CHANGELOG — MoAA-Prime

All notable changes to this repo, by phase.

## Cycle 001 — CLI + docs hard-polish
- Added module entrypoint: `src/moaa_prime/__main__.py`.
- Updated CLI parser to support:
  - `python -m moaa_prime "prompt"` (shorthand route mode)
  - explicit `hello|route|swarm` subcommands.
- Added safe JSON serialization for dataclass-containing outputs in CLI/demo paths.
- Added CLI behavior tests:
  - `tests/test_cli_module_entrypoint.py`
- Added `pytest.ini` (`pythonpath = src`) for local test discovery without editable install.
- Added install-time console script:
  - `moaa-prime` via `pyproject.toml`
- Added `ARCHITECTURE.md`.
- Replaced stale continuity docs (`README.md`, `MASTER_HANDOFF.md`, `FILEMAP.md`, `DEMO_README.md`) to match real paths and commands.
- Added autonomous Codex swarm launcher and prompt:
  - `scripts/run_swarm_cycle.sh`
  - `.codex/prompts/cycle-001.md`
  - `.codex/runs/` output location
- Hardened script execution from plain checkouts by prepending local `src/` in:
  - `scripts/demo_run.py`
  - `scripts/bench_run.py`
  - `scripts/eval_run.py`
- Made `reports/final_report.json` deterministic by sorting `agents_used`.
- Fixed `moaa_prime.memory.episodic` back-compat shim to export `Episode` safely.

## Phase 1 — Packaging + smoke
- Added src/ layout, minimal app entry, import smoke tests.

## Phase 2 — Agents + Contracts + Router
- Added Contract, BaseAgent, MathAgent, CodeAgent.
- Added MetaRouter with decision metadata.
- Added routing tests.

## Phase 3 — Oracle
- Added oracle verifier scaffolding + app wiring.
- Added oracle tests.

## Phase 4 — Swarm
- Added SwarmManager and swarm path in app.
- Added swarm tests.

## Phase 5 — Memory v1 (per-agent + global ReasoningBank)
- Wired ReasoningBank into app/agents (as implemented).
- Ensured BaseAgent returns memory meta required by tests:
  - local_hits
  - bank_hits
- Tests green.

## Phase 6 — E-MRE v1
- Added E-MRE scaffolding/hooks in memory layer:
  - AEDMC
  - SH-COS
  - GFO
  - curiosity bump hooks

## Phase 7 — SGM + Energy Fusion v0
- Added SharedGeometricManifold scaffolding.
- Added fusion scaffolding (v0).

## Phase 8 — Consolidation
- Stabilized interfaces while growing features; tests maintained.

## Phase 9 — SFC (Stability Field Controller)
- Added stability/budget coupling hooks (v0).

## Phase 10 — Dual-brain (Architect / Oracle split)
- Added dual-brain runner scaffolding + tests.

## Phase 11 — GCEL (Genetic Contract Evolution Loop)
- Added GCEL evolve() with elite selection, mutation, crossover.
- Enforced competence clamping to bounds.

## Phase 12 — Hard-polish demo + benchmarks
- Added eval runner + JSON report writer.
- Added demo script that writes a single demo JSON artifact.
- Added bench script that writes timing JSON.
- Added optional real model wiring via Ollama:
  - MOAA_LLM_PROVIDER=ollama
  - MOAA_OLLAMA_HOST
  - MOAA_OLLAMA_MODEL
- reports/ treated as generated output (gitignored).
