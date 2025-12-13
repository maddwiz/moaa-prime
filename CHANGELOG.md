# CHANGELOG — MoAA-Prime

## Unreleased

## Phase 5 — Memory v1 (DONE)
- Added ReasoningBank memory wiring into app + agents.
- Added per-agent lane writes and reads keyed by task_id.
- Added global/bank recall fields to satisfy Phase 5 contract:
  - local_hits, bank_hits, global_hits, items
- All tests passing: pytest (7 passed)

## Phase 4 — Swarm (DONE)
- SwarmManager added and wired into app/cli.
- Debate rounds + top_k routing (as implemented).

## Phase 3 — Oracle (DONE)
- OracleVerifier integrated so run_once includes oracle field/metadata.

## Phase 2 — Routing (DONE)
- Contracts, BaseAgent, MathAgent, CodeAgent, MetaRouter.

## Phase 1 — Packaging (DONE)
- src layout + import smoke tests + CLI entry.
