# MASTER HANDOFF — moaa-prime

## What this repo is
MoAA-Prime is a minimal, test-driven scaffold for a Mixture of Adaptive Agents system.
It starts tiny and grows by phases without breaking interfaces.

## Current phase status
✅ Phase 1 complete (as of 2025-12-12)

## What works right now
- `MoAAPrime.run_once(prompt)`:
  - routes prompt to one agent (MathAgent/CodeAgent)
  - returns decision + agent result + oracle score
- `MoAAPrime.run_swarm(prompt)`:
  - gets top-k candidate agents
  - runs each agent
  - oracle verifies each answer (via `verify`)
  - returns best + candidates list

## Key contracts we will NOT break
- Agent interface: `handle(prompt) -> AgentResult`
- Router interface:
  - `route(prompt) -> (agent, RouterDecision)`
  - `top_k(prompt, k) -> list[(agent, RouterDecision)]`
- Oracle interface:
  - `score(prompt, answer) -> OracleVerdict`
  - `verify(prompt, answer, agent_name=None) -> OracleVerdict`
- Swarm interface:
  - `run(prompt) -> dict(best=..., candidates=...)`

## Next phase plan (Phase 2)
- Expand routing logic beyond stub scoring
- Add prompt embedding + contract bidding (still deterministic)
- Keep tests green, add new tests for Phase 2

## MRE note (requested by Desmond)
Yes: MoAA agents will use the upgraded MRE (E-MRE: AEDMC + SH-COS + GFO + curiosity hook).
We will integrate it AFTER Phase 2 routing is stable, so memory doesn’t mask routing bugs.
