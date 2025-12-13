# FILEMAP — MoAA-Prime (update after every phase)

This maps the repo so a new chat window can re-sync instantly.

## Root
- MASTER_HANDOFF.md  -> living continuity doc (complete Phase 1 → current)
- FILEMAP.md         -> repo map (this file)
- CHANGELOG.md       -> phase-by-phase log
- pyproject.toml     -> packaging (src layout)
- scripts/           -> runnable demo/bench/eval scripts
- reports/           -> GENERATED outputs (gitignored)
- src/moaa_prime/    -> library code
- tests/             -> tests

## Core entrypoints
- src/moaa_prime/core/app.py        -> main app object (MoAAPrime)
- src/moaa_prime/cli/__main__.py    -> `python -m moaa_prime "prompt"`

## Major modules (by folder)
- src/moaa_prime/contracts/         -> Contract model
- src/moaa_prime/agents/            -> BaseAgent + domain agents
- src/moaa_prime/router/            -> MetaRouter + routing decisions
- src/moaa_prime/oracle/            -> truth scoring / verifier
- src/moaa_prime/swarm/             -> SwarmManager + runners (stable/duality)
- src/moaa_prime/memory/            -> ReasoningBank + E-MRE primitives/hooks
- src/moaa_prime/sgm/               -> SharedGeometricManifold (v0)
- src/moaa_prime/fusion/            -> fusion scaffolding (v0)
- src/moaa_prime/sfc/               -> stability/budget controller (v0)
- src/moaa_prime/brains/            -> Architect + Oracle brain stubs
- src/moaa_prime/duality/           -> duality utilities/hooks (if present)
- src/moaa_prime/evolution/         -> GCEL implementation
- src/moaa_prime/eval/              -> eval runner + report writer
- src/moaa_prime/llm/               -> LLMClient, Stub client, Ollama client, env factory
- src/moaa_prime/util/              -> helpers (rng, etc.)
- src/moaa_prime/utils/             -> misc helpers (if present)

## Scripts
- scripts/demo_run.py               -> writes reports/demo_run.json
- scripts/bench_run.py              -> writes reports/bench.json
- scripts/eval_run.py               -> writes reports/eval_report.json (generated)

## Tests (names may grow, but these are core)
- tests/test_phase1_smoke.py
- tests/test_phase2_router.py
- tests/test_phase3_oracle.py
- tests/test_phase4_swarm.py
- tests/test_phase5_memory.py
- tests/test_phase10_dual_brain.py
- tests/test_phase11_gcel.py
- tests/test_phase12_eval_smoke.py

