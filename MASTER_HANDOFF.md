# MASTER_HANDOFF — MoAA-Prime (living continuity doc)

Owner: Desmond
Local: DGX Spark
Rule: Always full-file replacements (no partial edits).

## What MoAA-Prime is
MoAA-Prime is a “Mixture of Adaptive Agents” system:

- Agents with contracts (domains/tools/competence)
- Router chooses agent(s) for prompts/tasks
- Oracle scores truth/quality
- Swarm manager runs multi-candidate deliberation and selects best
- Memory: per-agent lanes + global ReasoningBank
- E-MRE upgrades: AEDMC + SH-COS + GFO + curiosity bump
- SGM + Energy Fusion scaffolding
- SFC stability/budget hooks
- Dual-brain hooks (Architect / Oracle split)
- GCEL evolves contracts over time
- Eval harness produces demo-ready JSON reports

## Current truth snapshot
- `pytest -q` is passing (latest: 21 passed)
- `python scripts/eval_run.py` writes: `reports/eval_report.json`

## Continuity files (MUST stay complete)
- MASTER_HANDOFF.md (this file)
- FILEMAP.md
- CHANGELOG.md

---

## Phases (truth status)

### Phase 1 — Packaging + smoke (DONE)
Packaging + smoke tests.

### Phase 2 — Agents + Contracts + Router (DONE)
Contracts, BaseAgent, MathAgent/CodeAgent, MetaRouter.

### Phase 3 — Oracle (DONE)
OracleVerifier wired so run_once includes oracle info.

### Phase 4 — Swarm (DONE)
SwarmManager + app.run_swarm returns best + candidates.

### Phase 5 — Memory v1 (DONE)
Per-agent lanes + global ReasoningBank; task_id continuity.

### Phase 6 — E-MRE v1 (DONE)
AEDMC, SH-COS, GFO, curiosity bump integrated into memory approach.

### Phase 7 — SGM + Energy Fusion v0 (DONE)
SharedGeometricManifold + EnergyFusion scaffolding and tests.

### Phase 8 — Consolidation (DONE)
Compatibility pass so newer hooks don’t break earlier contracts/tests.

### Phase 9 — SFC (DONE / v0)
StabilityFieldController + StableSwarmRunner + CLI; SwarmManager supports router OR direct list.

### Phase 10 — Dual-brain (DONE / v0)
Architect/Oracle split runner scaffolding + tests.

### Phase 11 — GCEL (DONE)
Genetic Contract Evolution Loop (elite selection, mutation, crossover) with competence clamping; wired into app.

### Phase 12 — Eval + Demo (DONE)
EvalRunner executes “once” and “swarm” cases and writes JSON report:
- Run: `python scripts/eval_run.py`
- Output: `reports/eval_report.json`

