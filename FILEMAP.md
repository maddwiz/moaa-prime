# FILEMAP — MoAA-Prime
Update at the end of each phase.

## Root
- MASTER_HANDOFF.md  -> living handoff / continuity (update after each phase)
- FILEMAP.md         -> map of files (this file)
- CHANGELOG.md       -> changes per phase
- pyproject.toml     -> packaging (src layout)
- src/moaa_prime/... -> library code
- tests/...          -> tests

## Core entrypoints
- src/moaa_prime/core/app.py     -> main app object (MoAAPrime)
- src/moaa_prime/cli/__main__.py -> CLI entry (python -m moaa_prime "prompt")

## Phase 1 (DONE)
- tests/test_imports.py
- tests/test_phase1_smoke.py

## Phase 2 (DONE)
- src/moaa_prime/contracts/contract.py
- src/moaa_prime/agents/base.py
- src/moaa_prime/agents/math_agent.py
- src/moaa_prime/agents/code_agent.py
- src/moaa_prime/router/meta_router.py
- tests/test_phase2_router.py

## Phase 3 (DONE)
- src/moaa_prime/oracle/verifier.py
- tests/test_phase3_oracle.py

## Phase 4 (DONE)
- src/moaa_prime/swarm/manager.py
- tests/test_phase4_swarm.py

## Phase 5 (DONE) — Memory v1 (Option 2: per-agent + global bank)
- src/moaa_prime/memory/reasoning_bank.py (or equivalent in src/moaa_prime/memory/)
- src/moaa_prime/agents/base.py (memory read/write behavior + meta schema)
- src/moaa_prime/core/app.py (bank wired into agents)
- tests/test_phase5_memory.py

## Next phases (planned)
- Phase 6: E-MRE upgrade (AEDMC + SH-COS + GFO) + ReasoningBank schema upgrades
- Phase 7: SGM (shared manifold) + Energy fusion
- Phase 8: SFC (stability field controller)
- Phase 9: Seeker (OOD) + spawn hooks
- Phase 10: GCEL (genetic contracts evolution)
- Phase 11: Duality brain (Architect/Oracle split) applied across routing + debate
- Phase 12: Eval harness + demo runner + minimal UI
