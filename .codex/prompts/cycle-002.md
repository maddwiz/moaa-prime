You are in repo: maddwiz/moaa-prime.

BRANCH:
Create and work on branch: codex/swarm-cycle-002

GOLDEN RULES (non-negotiable):
- FULL FILE REPLACEMENTS ONLY (no partial edits).
- Keep tests deterministic by default (stub model).
- After work: update MASTER_HANDOFF.md + FILEMAP.md + CHANGELOG.md, run pytest -q, commit.
- Preserve optional Ollama wiring via env vars (MOAA_LLM_PROVIDER, MOAA_OLLAMA_HOST, MOAA_OLLAMA_MODEL).
(Reference: MASTER_HANDOFF describes these constraints and scripts outputs.)

MISSION (Cycle 2: "Real MoAA lift"):
Upgrade Router + Oracle + Swarm + Contract Evolution so they:
- produce measurable routing decisions
- have calibrated scoring signals
- support exploration vs exploitation
- support budget constraints (latency/cost tokens)
- evolve agent contracts only when it improves eval outcomes

REQUIRED OUTPUTS:
- A/B mode: allow running old vs new logic via flag or config
- Eval scripts produce a JSON report showing lift metrics between v1 and v2
- New unit tests that lock down determinism and core invariants

AGENT ROLES (spawn parallel):
1) ARCHITECT:
   - Write ARCHITECTURE_CYCLE2.md: exact data flow + interfaces for RouterV2, OracleV2, SwarmV2, GCELV2.
   - Define "routing score formula" and "oracle rubric" as stable docs.
   - Identify the cleanest injection points in current code.

2) ROUTER BUILDER:
   - Implement RouterV2:
     - Inputs: prompt/task metadata, agent contracts (domain/tools/competence), memory hints, budget (latency/cost), history stats.
     - Outputs: ranked agents + rationale + exploration probability + expected utility.
   - Deterministic default: use a seeded PRNG for exploration and deterministic heuristics.
   - Optional: if MOAA_LLM_PROVIDER=ollama, allow "LLM-assisted routing explanation" but never required for tests.

3) ORACLE BUILDER:
   - Implement OracleV2 scoring:
     - Score: [0,1]
     - Components (weighted): correctness proxy, coherence, constraint adherence, safety/overreach, citation/grounding if applicable.
     - Add a consistency check: if the same candidate is scored twice, variance should be near zero under stub.
   - Provide a pluggable rubric config (YAML/JSON) with defaults.

4) SWARM BUILDER:
   - Implement SwarmV2:
     - Generate N candidates (using existing mechanism)
     - Use OracleV2 to score each
     - Optionally: run 1 "cross-check" round where top-2 critique each other (stubbed by default)
     - Select best candidate with confidence + explanation
   - Must surface structured trace (router decision, candidates, oracle scores, selection).

5) GCEL / CONTRACTS BUILDER:
   - Implement GCELV2 contract evolution:
     - Each agent contract has fields: domains, tools, competence tags, reliability prior, cost prior
     - Fitness = rolling aggregate of oracle score + success rate under eval + budget efficiency
     - Evolution step: propose small mutations (add/remove tag/tool/domain weight), then accept ONLY if eval improves (gated)
   - Deterministic by default (seeded).

6) TESTER:
   - Add tests:
     - RouterV2 returns stable ranking given seed and fixed inputs
     - OracleV2 scoring is stable and bounded
     - SwarmV2 selects highest-scoring candidate
     - GCELV2 does not mutate contract if fitness does not improve
   - Ensure pytest -q passes.

7) EVAL / REPORT:
   - Extend scripts/eval_run.py (or add a new scripts/eval_compare.py) to run:
     - v1 baseline vs v2 upgraded, same dataset slice, same seed
     - Output: reports/eval_compare.json with metrics:
       - avg_oracle_score
       - win_rate_v2_over_v1 (pairwise)
       - routing_entropy (exploration)
       - avg_cost/latency proxies (even if mocked)
   - Ensure reports/ is gitignored.

8) DEBUGGER:
   - Standby to fix failures from any agent work quickly.

PROCESS:
- Spawn agents above in parallel.
- Wait for all.
- Merge outputs.
- Run:
  - pytest -q
  - python scripts/demo_run.py
  - python scripts/bench_run.py
  - python scripts/eval_run.py
  - (new) python scripts/eval_compare.py  (if created)
- Update MASTER_HANDOFF.md + FILEMAP.md + CHANGELOG.md with Cycle 2 truth and new commands.
- Commit message: "swarm: cycle-002 router/oracle/swarm/gcel v2 + eval compare"
- Print final summary with exact commands and where reports are written.

EXTRA UPGRADE:
Add a trace schema that every run emits (even stub runs):

reports/trace_<runid>.json containing:
- router: ranked agents + expected utility
- swarm: candidates + prompts used
- oracle: per-candidate component scores
- final: selected output + confidence
