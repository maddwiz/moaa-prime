# FILEMAP — MoAA-Prime

This file maps the repo. Update at the end of each phase.

## Root
- MASTER_HANDOFF.md  -> living handoff / continuity (update after each phase)
- FILEMAP.md         -> map of files (this file)
- CHANGELOG.md       -> log of changes per phase
- pyproject.toml     -> packaging (src layout)
- src/moaa_prime/... -> library code
- tests/...          -> tests

## Core entrypoints
- src/moaa_prime/core/app.py     -> main app object (MoAAPrime)
- src/moaa_prime/cli/__main__.py -> CLI entry (python -m moaa_prime "prompt")

## Phase 1 scope (DONE)
- packaging + import smoke tests

## Phase 2 scope (DONE)
- contracts + base agents + meta-router

## Phase 3 scope (DONE)
- oracle verifier + wiring

## Phase 4 scope (DONE)
- swarm manager + CLI command + tests

## Phase 5 scope (DONE)
- memory v1: per-agent memory lanes + global ReasoningBank

## Phase 6 scope (DONE)
- src/moaa_prime/memory/episodic_lane.py     -> E-MRE lane (AEDMC + curiosity bump + SH-COS + GFO)
- src/moaa_prime/memory/reasoning_bank.py    -> global bank + per-lane recall (kl_like + SH-COS text)
- src/moaa_prime/agents/base.py              -> preserved Phase 5 memory contract, enriched for Phase 6
- tests/*                                    -> still green

## Next phase (NOW)
- Phase 7: SGM (Shared Geometric Manifold) + Energy Fusion v0 (minimal + testable)

