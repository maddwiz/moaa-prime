# MASTER HANDOFF — MoAA-Prime
Status: AUTHORITATIVE CONTINUITY DOCUMENT  
Update Rule: MUST be fully rewritten at the end of every phase

---

## What is MoAA-Prime?

MoAA-Prime (Mixture of Adaptive Agents) is an agentic swarm architecture that evolves beyond Mixture-of-Experts by adding:

- Explicit agents (not hidden experts)
- Contracts + routing
- Swarm deliberation
- Oracle-based truth gating
- Long-horizon memory (E-MRE)
- Stability control (SFC)
- Energy-based fusion (SGM)
- Dual-brain reasoning (Architect / Oracle)
- Evolutionary mutation (GCEL)
- Verifiable evaluation

The goal is **resilient, long-horizon, truth-anchored reasoning** — not token prediction.

---

## CURRENT TRUTH SNAPSHOT (DO NOT ARGUE THIS)

### ✅ Completed Phases

**Phase 1 — Packaging & Smoke**
- Repo initialized (src layout)
- MoAAPrime app object
- CLI smoke command
- Import + smoke tests

**Phase 2 — Agents, Contracts, Router**
- BaseAgent abstraction
- MathAgent / CodeAgent
- Contract model (domains, competence, tools)
- MetaRouter (embedding + competence routing)
- Routing tests

**Phase 3 — Oracle**
- OracleVerifier abstraction
- Default oracle behavior
- Oracle wired into routing
- Oracle tests

**Phase 4 — Swarm**
- SwarmManager
- Multi-agent deliberation
- Oracle-scored candidate selection
- Swarm CLI command
- Swarm tests

**Phase 5 — Memory v1**
- Per-agent memory lanes
- Global ReasoningBank
- Carry-Over Summaries (COS)
- Entropy-driven history depth (AEDMC-lite)
- Retrieval tests

**Phase 6 — E-MRE v1**
- Adaptive Entropy-Driven Markov Chains (AEDMC)
- Superposed Hierarchical COS (SH-COS)
- Geometric Forgetting Oracle (GFO)
- Curiosity bump (cross-lane recall on KL divergence)
- Rot-resistance verified by tests

**Phase 7 — SGM + Energy Fusion**
- SharedGeometricManifold (hyperbolic embedding)
- EnergyFusion (consistency + diversity)
- Fusion-aware swarm selection
- Non-breaking optional wiring

**Phase 8 — Stable Fusion Integration**
- Fusion wired into swarm loop
- Energy tracked in metadata
- Fusion remains optional & test-safe

**Phase 9 — Stability Field Controller (SFC)**
- StabilityFieldController
- StableSwarmRunner
- Early-stop on instability
- Budget-aware swarm execution
- CLI: phase9_stable_cmd
- SwarmManager now supports:
  - MetaRouter OR
  - Direct agent list (for tests + experiments)

---

## What We Just Verified

- ALL TESTS PASS (15/15)
- SwarmManager signature mismatch FIXED
- Phase 9 CLI executes correctly
- Repo pushed and pulled cleanly
- No phantom phases
- No skipped work

---

## NEXT PHASES (NOT STARTED YET)

**Phase 10 — Dual-Brain Reasoning**
- Architect agent (planning / structure)
- Oracle-critic agent (truth / challenge)
- Deliberate tension, not consensus
- Brain-split wiring inside swarm

**Phase 11 — GCEL (Genetic Contract Evolution Loop)**
- Contract mutation
- Fitness via oracle + SFC
- Specialization over time

**Phase 12 — Evaluation & Demo**
- GAIA subset
- WebArena mini
- Ablations
- Demo script + video

---

## Non-Negotiable Rules Going Forward

1. **Full-file replacements only**
2. **No partial continuity docs**
3. **Never rewind phases**
4. **Never overwrite without explicit instruction**
5. **5-year-old mode for all terminal steps**
6. **Tests define truth**

If a future assistant contradicts this file, THIS FILE WINS.

