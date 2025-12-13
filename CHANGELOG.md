# CHANGELOG — MoAA-Prime

All notable changes to this repo, by phase.

## Phase 1 — Packaging + smoke
- Created src/ layout + core app entry
- Added smoke tests for imports and app hello

## Phase 2 — Agents + Contracts + Router
- Added Contract model
- Added BaseAgent + MathAgent + CodeAgent
- Added MetaRouter with route() returning (agent, decision)
- Added Phase 2 router tests

## Phase 3 — Oracle
- Added OracleVerifier (truth scoring hooks)
- Wired oracle into app outputs
- Added oracle tests

## Phase 4 — Swarm
- Added SwarmManager
- Added run_swarm wiring + tests

## Phase 5 — Memory (Per-agent + Global ReasoningBank)
- Added per-agent memory lanes (via bank usage)
- Added global ReasoningBank to app
- Added tests for memory read/write behaviors

## Phase 6 — E-MRE v1
- Added AEDMC (entropy-driven k)
- Added SH-COS (multi-level COS)
- Added GFO pruning rules
- Added curiosity bump hooks (cross-lane pulls)

## Phase 7 — SGM + Energy Fusion v0
- Added SharedGeometricManifold scaffolding
- Added EnergyFusion scaffolding + tests

## Phase 8 — Consolidation
- Kept tests stable while extending swarm fusion paths

## Phase 9 — SFC (Stability Field Controller)
- Added StabilityFieldController (budget/health tracking)
- Added StableSwarmRunner + CLI command
- Made SwarmManager.run compatible with router OR direct agent list
- Updated continuity docs; tests green

## Phase 10 — Dual-brain (Architect / Oracle split)
- Added dual-brain runner scaffolding + tests

## Phase 11 — GCEL (Genetic Contract Evolution Loop)
- Added GCEL evolve() (elite selection, mutation, crossover)
- Ensured competence clamped to [0.05, 0.99]
- Wired evolve_contracts() into app
- Tests green

## Phase 12 — Eval + Demo (DONE)
- Added eval runner (EvalRunner + EvalCase + EvalResult)
- Added JSON report writer
- Added scripts/eval_run.py to generate reports/eval_report.json
- Added Phase 12 eval smoke test
