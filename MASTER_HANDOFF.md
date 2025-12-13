# MASTER_HANDOFF — MoAA-Prime (living)

Owner: Desmond
Local path: ~/moaa-prime
Goal: MoAA-Prime = MoE evolved into a swarm of adaptive agents with verifiable routing, memory (E-MRE), geometry (SGM), stability (SFC), dual-brain, and evolution (GCEL).

## Golden rules (Dev workflow)
- Full-block replacements only (no partial line edits).
- Always keep continuity docs COMPLETE (Phase 1 → current).
- After each phase: update MASTER_HANDOFF.md + FILEMAP.md + CHANGELOG.md, run tests, commit.

## How to run
### Tests
pytest -q

### CLI (current)
python -m moaa_prime "your prompt"

## Roadmap status (truth snapshot)
### Phase 1 — Packaging + smoke ✅
- src layout + import smoke tests + minimal app object.

### Phase 2 — Agents + Contracts + Router ✅
- Contracts, BaseAgent, MathAgent, CodeAgent, MetaRouter routing.

### Phase 3 — Oracle ✅
- Oracle verifier wired and tested.

### Phase 4 — Swarm ✅
- SwarmManager + swarm CLI wiring + tests.

### Phase 5 — Memory v1 ✅ (per-agent + global ReasoningBank)
- Per-agent memory hooks + ReasoningBank integration.
- Tests expect result.meta["memory"] includes: local_hits, bank_hits.
- Current status: pytest passes (21 passed).

### Phase 6 — E-MRE v1 (AEDMC + SH-COS + GFO + curiosity bump)
- Implemented in repo per FILEMAP/CHANGELOG (see those files for exact modules).

### Phase 7 — SGM + Energy Fusion v0
- Implemented in repo per FILEMAP/CHANGELOG.

### Phase 8 — SFC (stability budgets)
- Implemented in repo per FILEMAP/CHANGELOG.

### Phase 9 — Dual-brain (Architect / Oracle)
- Implemented in repo per FILEMAP/CHANGELOG.

### Phase 10 — GCEL mutations
- Implemented in repo per FILEMAP/CHANGELOG.
- NOTE: Needs cleanup pass (naming, docs, guardrails) before final demo polish.

### Phase 11 — Eval scaffolding
- Implemented in repo per FILEMAP/CHANGELOG.

### Phase 12 — Demo + benchmarks (CURRENT PHASE)
- You chose: C) hard-polish demo + benchmarks + wire real models (optional).

## Current known issue(s)
- NONE blocking tests right now (all tests passing).
- Next risk: wiring “real LLMs” must be optional so tests remain fast/offline.

## What we do next (Phase 12C checklist)
1) Create a "demo runner" that exercises: router → swarm → memory → fusion → budgets → duality → (optionally) GCEL.
2) Create a "bench runner" that logs latency + token counts + memory hits + oracle scores.
3) Wire "real model" behind an env var so default is StubLLMClient.
4) Produce a clean demo command sequence (recordable).
5) Freeze: tag release, push to GitHub.

