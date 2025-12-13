# CHANGELOG — MoAA-Prime

## Phase 1 — Packaging + smoke
- Added src/ layout, minimal app, import smoke tests.

## Phase 2 — Agents + contracts + router
- Added Contract, BaseAgent, MathAgent, CodeAgent.
- Added MetaRouter and routing decision metadata.
- Added tests covering routing.

## Phase 3 — Oracle
- Added verifier (math/code/general stubs) and wired into app.
- Added oracle tests.

## Phase 4 — Swarm
- Added SwarmManager with debate loop.
- Added CLI swarm entry (if present) + tests.

## Phase 5 — Memory v1 (per-agent + global ReasoningBank)
- Added ReasoningBank integration.
- Ensured BaseAgent result.meta["memory"] includes:
  - local_hits
  - bank_hits
- Verified: pytest passes (21 passed) after BaseAgent memory meta fixes.

## Phase 6 — E-MRE v1 (AEDMC + SH-COS + GFO + curiosity bump)
- Implemented E-MRE primitives and wired through memory layer.

## Phase 7 — SGM + Energy Fusion v0
- Added geometric manifold state + fusion scoring.

## Phase 8 — SFC
- Added stability budget + pruning triggers.

## Phase 9 — Dual-brain
- Added Architect/Oracle brain split + gate.

## Phase 10 — GCEL
- Added genetic contract mutation / specialization logic.
- TODO: cleanup pass in Phase 12C (naming, docs, safety rails).

## Phase 11 — Eval scaffolding
- Added basic eval runner hooks + metrics stubs.

## Phase 12 (current) — Demo + benchmarks polish
- Next: add scripts/ demo runner + benchmarks, then wire optional real models behind env var.

