# FILEMAP — MoAA-Prime (update after every phase)

## Root
- MASTER_HANDOFF.md  -> living handoff / continuity (complete)
- FILEMAP.md         -> repo map (this file)
- CHANGELOG.md       -> phase-by-phase log
- pyproject.toml     -> packaging (src layout)
- src/moaa_prime/... -> library code
- tests/...          -> tests

## Core entrypoints
- src/moaa_prime/core/app.py   -> main app object (MoAAPrime)
- src/moaa_prime/cli/__main__.py -> python -m moaa_prime "...prompt..."

## Core building blocks (high level)
- src/moaa_prime/contracts/     -> Contract + related typing
- src/moaa_prime/agents/        -> BaseAgent + domain agents
- src/moaa_prime/router/        -> MetaRouter + routing decisions
- src/moaa_prime/oracle/        -> verifiers / truth scoring
- src/moaa_prime/swarm/         -> swarm manager + debate loops
- src/moaa_prime/memory/        -> ReasoningBank + E-MRE primitives
- src/moaa_prime/sgm/           -> Shared Geometric Manifold + energy fusion
- src/moaa_prime/sfc/           -> stability / budget coupling
- src/moaa_prime/duality/       -> architect/oracle split
- src/moaa_prime/gcel/          -> genetic contracts / evolution
- src/moaa_prime/evals/         -> eval runners + metrics
- src/moaa_prime/llm.py         -> LLMClient + StubLLMClient (real models later, optional)

## Tests
- tests/test_phase1_smoke.py
- tests/test_phase2_router.py
- tests/test_phase3_oracle.py
- tests/test_phase4_swarm.py
- tests/test_phase5_memory.py
- (phase 6+ tests live under tests/ as present in repo)

