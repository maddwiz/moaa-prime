# MASTER_HANDOFF — MoAA-Prime (Living Continuity Doc)

## What this repo is
MoAA-Prime is a Mixture of Adaptive Agents system (agents + router + oracle + swarms + memory).
Goal: build a verifiable, adaptive swarm architecture that can later scale toward MoAA-Prime features
(SGM/SFC/Seeker/GCEL/Duality + E-MRE memory).

## Current status (as of now)
- Phases complete: 1, 2, 3, 4, 5
- Tests: `pytest -q` -> **7 passed**
- Phase 5 memory behavior:
  - Each agent can write to memory using prompts like "Remember: ..."
  - Each agent can read memory on "What was the answer?" style prompts
  - Memory meta schema includes: local_hits, bank_hits, global_hits, items

## How to run
### Run tests
pytest -q

### Run a prompt once (CLI)
python -m moaa_prime "Remember: the answer is 42"
python -m moaa_prime "What was the answer?"

## Key files
- src/moaa_prime/core/app.py
- src/moaa_prime/agents/base.py
- src/moaa_prime/router/meta_router.py
- src/moaa_prime/swarm/manager.py
- src/moaa_prime/oracle/verifier.py
- src/moaa_prime/memory/*

## Next phase (Phase 6)
Upgrade Phase 5 “memory v1” into E-MRE v1:
- AEDMC: adaptive Markov order (k=1..5) driven by entropy/perplexity
- SH-COS: multi-level COS (episodic/mid/semantic)
- GFO: forgetting oracle (manifold/anchor guided pruning)
- Integrate global ReasoningBank queries into routing + Seeker triggers

