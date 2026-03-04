# CHANGELOG — MoAA-Prime

All notable changes to this repo, by phase.

## Cycle 003A — Nonstop Codex swarm automation
- Added nonstop swarm daemon script: `scripts/swarm_autopilot.sh`.
  - `start|stop|status|tail|once|run` controls.
  - Continuous loop with cycle state, heartbeat, summary TSV, and daemon logs.
  - Automatic fallback prompt switching after configurable failure streak.
  - Validation gating modes (`auto|quick|full|none`) and optional auto-commit/auto-push.
- Added default continuous mission prompt: `.codex/prompts/autopilot.md`.
- Updated runbook docs (`README.md`, `MASTER_HANDOFF.md`, `FILEMAP.md`) for nonstop swarm operation.

## Cycle 003 — Learning system (RouterV3 + traces + Pareto + training)
- Added `ARCHITECTURE_CYCLE3.md` with full Cycle 3 data flow and interfaces.
- Added RouterV3 (`src/moaa_prime/router/router_v3.py`) with:
  - learned expected-success model (`RouterV3Model`)
  - deterministic local model load/save (`models/router_v3.pt`)
  - adaptive budget profiles (`cheap`, `balanced`, `max_quality`)
  - embedding + history + budget feature scoring
- Added deterministic embedding utilities (`src/moaa_prime/router/embeddings.py`) for:
  - task embedding
  - contract embedding
  - cosine similarity
- Added router training pipeline (`src/moaa_prime/router/training.py`) and script:
  - `scripts/train_router.py`
  - writes `reports/router_train_report.json` + `models/router_v3.pt`
- Added trace recorder (`src/moaa_prime/trace/recorder.py`) and app wiring so every swarm run writes:
  - `reports/traces/run_<id>.json`
  - `datasets/router_training.jsonl`
- Extended contract schema (`src/moaa_prime/contracts/contract.py`) with:
  - `tags`
  - `description`
  - `embedding`
- Upgraded swarm manager (`src/moaa_prime/swarm/manager.py`) with v3 behavior:
  - candidate confidence proxy
  - optional cross-critique hooks
  - Pareto frontier selection by score/confidence/latency/cost
  - budget-mode-aware final candidate utility
- Added Pareto helper module: `src/moaa_prime/swarm/pareto.py`.
- Upgraded app composition root (`src/moaa_prime/core/app.py`) to support:
  - mode `v3`
  - RouterV3/SwarmV3 wiring
  - budget mode propagation
  - training trace + dataset append on swarm runs
- Added RouterV2 vs RouterV3 evaluation script:
  - `scripts/eval_router.py`
  - writes `reports/eval_router.json` metrics:
    - `routing_accuracy`
    - `oracle_score_gain`
    - `latency_efficiency`
    - `cost_efficiency`
- Updated runnable defaults to showcase Cycle 3 (`v3`) in:
  - `scripts/demo_run.py`
  - `scripts/bench_run.py`
  - `scripts/eval_run.py`
- Added deterministic Cycle 3 tests:
  - `tests/test_cycle3_router_training.py`
  - `tests/test_cycle3_router_v3.py`
  - `tests/test_cycle3_pareto.py`
  - `tests/test_cycle3_trace_recorder.py`
- Updated `.gitignore` to exclude generated `datasets/` artifacts.

## Cycle 002 — Real MoAA lift (Router/Oracle/Swarm/GCEL v2)
- Added `ARCHITECTURE_CYCLE2.md` with exact v2 data flow, interfaces, formulas, and rubric.
- Added RouterV2 (`src/moaa_prime/router/router_v2.py`) with:
  - deterministic seeded scoring
  - exploration vs exploitation probability
  - budget/history/memory-aware expected utility
  - ranked rationale + component breakdown
- Added OracleV2 in `src/moaa_prime/oracle/verifier.py` with:
  - weighted `[0,1]` rubric components (`correctness_proxy`, `coherence`, `constraint_adherence`, `safety_overreach`, `grounding`)
  - consistency check API for repeated scoring variance
  - pluggable JSON/YAML rubric support
  - bundled default rubric file `src/moaa_prime/oracle/rubric_v2.yaml`
- Upgraded swarm manager (`src/moaa_prime/swarm/manager.py`) for mode-aware v1/v2 execution:
  - v2 candidate generation/scoring/selection
  - optional top-2 cross-check round (stubbed unless enabled)
  - confidence estimation
  - structured trace payload (`router/swarm/oracle/final`)
- Extended contract schema (`src/moaa_prime/contracts/contract.py`) with `reliability` and `cost_prior` priors.
- Added GCELV2 in `src/moaa_prime/evolution/gcel.py`:
  - fitness aggregation across oracle/eval/budget
  - bounded deterministic mutations
  - gated acceptance only on evaluator improvement
- Upgraded app composition root (`src/moaa_prime/core/app.py`) to support A/B mode wiring and trace file emission:
  - `reports/trace_<runid>.json`
- Upgraded eval stack:
  - `src/moaa_prime/eval/runner.py` mode-aware with oracle/entropy/cost/latency proxies
  - `src/moaa_prime/eval/report.py` aggregate metrics
  - `scripts/eval_compare.py` for v1 vs v2 lift report (`reports/eval_compare.json`)
- Added deterministic Cycle 2 tests:
  - `tests/test_cycle2_router_v2.py`
  - `tests/test_cycle2_oracle_v2.py`
  - `tests/test_cycle2_swarm_v2.py`
  - `tests/test_cycle2_gcel_v2.py`

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
