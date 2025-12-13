# MASTER_HANDOFF — MoAA-Prime (living continuity doc)

Owner: Desmond
Local path: ~/moaa-prime

Golden rules:
- FULL FILE REPLACEMENTS ONLY (no partial edits).
- Continuity docs must be COMPLETE (Phase 1 → current).
- After each phase: update MASTER_HANDOFF.md + FILEMAP.md + CHANGELOG.md, run tests, commit.

---

## What MoAA-Prime is (current)
MoAA-Prime is a “Mixture of Adaptive Agents” system:

- Agents with contracts (domains/tools/competence)
- Router chooses agent(s) for prompts/tasks
- Oracle scores truth/quality
- Swarm manager runs multi-candidate deliberation
- Memory: per-agent lanes + global ReasoningBank
- E-MRE upgrades: AEDMC + SH-COS + GFO + curiosity bump hooks
- SGM + Energy Fusion scaffolding
- SFC stability/budget hooks
- Dual-brain hooks (Architect / Oracle split)
- GCEL evolves contracts over time
- Eval + demo + bench scripts for a “hard-polish” demo bundle
- Optional real model wiring via Ollama (keeps tests passing by default)

---

## Current truth snapshot (verify anytime)
Run tests:
  pytest -q

Known-good state:
- pytest passes (latest seen: 21 passed)
- demo script writes: reports/demo_run.json
- bench script writes: reports/bench.json
- with Ollama enabled, bench runs slower (real model latency)

---

## How to run (simple)

### 1) Tests
pytest -q

### 2) CLI (quick)
python -m moaa_prime "your prompt"

### 3) Demo bundle (writes JSON artifacts)
python scripts/demo_run.py
# output: reports/demo_run.json

### 4) Bench (writes timing JSON)
python scripts/bench_run.py
# output: reports/bench.json

---

## Real model wiring (Ollama) — optional
Default = stub model (tests stay fast + deterministic).

Enable Ollama:
export MOAA_LLM_PROVIDER=ollama
export MOAA_OLLAMA_HOST="http://127.0.0.1:11434"
export MOAA_OLLAMA_MODEL="llama3.1:8b-instruct-q4_K_M"

Sanity check installed models:
curl -s http://127.0.0.1:11434/api/tags | head

Then run:
python scripts/demo_run.py
python scripts/bench_run.py

Note:
- If you pick the wrong model name, calls can fail.
- Your working model (seen in /api/tags) is: llama3.1:8b-instruct-q4_K_M

---

## Phases (truth status)

### Phase 1 — Packaging + smoke ✅
- src layout + minimal app + import smoke tests

### Phase 2 — Agents + Contracts + Router ✅
- Contract model
- BaseAgent + MathAgent + CodeAgent
- MetaRouter returns decision metadata

### Phase 3 — Oracle ✅
- Oracle verifier wired into outputs + tests

### Phase 4 — Swarm ✅
- SwarmManager multi-candidate path + tests

### Phase 5 — Memory v1 ✅
- Per-agent memory hooks + global ReasoningBank
- Tests expect result.meta["memory"] includes:
  - local_hits
  - bank_hits

### Phase 6 — E-MRE v1 ✅
- AEDMC / SH-COS / GFO scaffolding + curiosity bump hooks (as implemented in memory layer)

### Phase 7 — SGM + Energy Fusion v0 ✅
- Shared geometric manifold + fusion scaffolding (v0)

### Phase 8 — Consolidation ✅
- Stabilized interfaces + tests as the system grew

### Phase 9 — SFC ✅
- Stability/budget coupling hooks (v0)

### Phase 10 — Dual-brain ✅
- Architect / Oracle split runner scaffolding (v0)

### Phase 11 — GCEL ✅
- Genetic Contract Evolution Loop (elite selection + mutation + crossover + clamping)

### Phase 12 — Hard-polish demo + benchmarks ✅
- Eval runner + JSON report writer
- Demo script + bench script
- Optional real model provider wiring (Ollama)
- reports/ is generated output and should not be committed

---

## Repo hygiene notes
- reports/ is GENERATED. It should be gitignored.
- Keep small phases: change → tests → commit.

