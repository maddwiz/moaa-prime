# MASTER HANDOFF — MoAA-Prime (Living)

## What this repo is
MoAA-Prime is a modular “Mixture of Adaptive Agents” system:
- Multiple agents with contracts (competence/domains/tools)
- Router selects agents
- Oracle verifies
- Swarm manager supports multi-agent deliberation
- Memory is per-agent + global ReasoningBank
- We are building phase-by-phase with tests + continuity docs

## Current Status (as of Phase 6)
✅ Phase 1–6 complete and tests passing.

### Implemented
- Contracts + Agents:
  - MathAgent, CodeAgent (BaseAgent shared behavior)
- Router:
  - MetaRouter routes prompt to best agent (Phase 2)
- Oracle:
  - Verifier scaffold wired (Phase 3)
- Swarm:
  - Swarm manager exists + CLI command (Phase 4)
- Memory:
  - Phase 5: per-agent lanes + global ReasoningBank
  - Phase 6: E-MRE v1 inside lanes:
    - AEDMC-lite (entropy -> Markov order k)
    - Curiosity bump (+1 order when high entropy + novel)
    - SH-COS (multi-level summaries) returned as global_text
    - GFO pruning to keep memory bounded
  - ReasoningBank remains backward compatible

## Phase Rules (IMPORTANT)
- Always replace FULL blocks of code (no partial line edits).
- After each phase:
  1) run tests
  2) update CHANGELOG.md, FILEMAP.md, MASTER_HANDOFF.md
  3) git commit + push

## Next Up: Phase 7
Goal: Add SGM + Energy Fusion v0 (minimal):
- SGM: shared geometric embedding space for agent outputs / memory summaries
- Energy Fusion: combine multiple candidate answers using simple energy score
- Wire into swarm manager (optional) with a tiny switch: fusion=energy|oracle_max
- Add tests:
  - SGM returns stable vector for same input
  - energy fusion selects best candidate given oracle scores

