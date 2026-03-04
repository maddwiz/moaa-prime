You are in repo: maddwiz/moaa-prime.

CRITICAL EXECUTION MODE:
- Execute this cycle as a SINGLE DIRECT AGENT.
- DO NOT use sub-agent tools (`spawn_agent`, `send_input`, `wait`).
- If a tool is unavailable, do not retry in loops; continue with direct implementation.
- Do not emit no-op shell spam.

BRANCH:
Create and work on branch: codex/swarm-cycle-002

GOLDEN RULES (non-negotiable):
- FULL FILE REPLACEMENTS ONLY (no partial edits).
- Keep tests deterministic by default (stub model).
- After work: update MASTER_HANDOFF.md + FILEMAP.md + CHANGELOG.md, run pytest -q, commit.
- Preserve optional Ollama wiring via env vars (MOAA_LLM_PROVIDER, MOAA_OLLAMA_HOST, MOAA_OLLAMA_MODEL).

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

IMPLEMENTATION TARGETS:
1) ARCHITECT:
   - Write ARCHITECTURE_CYCLE2.md: exact data flow + interfaces for RouterV2, OracleV2, SwarmV2, GCELV2.
   - Define routing score formula and oracle rubric.

2) ROUTER V2:
   - Implement RouterV2 with inputs: prompt/task metadata, contracts, memory hints, budget, history stats.
   - Outputs: ranked agents + rationale + exploration probability + expected utility.
   - Deterministic default via seeded PRNG.

3) ORACLE V2:
   - Score [0,1] with weighted components: correctness proxy, coherence, constraint adherence, safety/overreach, grounding.
   - Consistency check for repeated scoring (low variance under stub).
   - Pluggable rubric config JSON/YAML.

4) SWARM V2:
   - Generate N candidates, score via OracleV2, optional top-2 cross-check round (stub by default), select best with confidence.
   - Emit structured trace: router decision, candidates, oracle scores, final selection.

5) GCEL V2:
   - Contract fields include reliability and cost priors.
   - Fitness aggregates oracle score + eval success + budget efficiency.
   - Propose small mutations, accept only if eval improves (gated).
   - Deterministic by default (seeded).

6) TESTS:
   - Add deterministic tests for RouterV2, OracleV2, SwarmV2 selection, GCELV2 gating.

7) EVAL / REPORT:
   - Add scripts/eval_compare.py (or equivalent) for v1 vs v2, same seed/dataset slice.
   - Write reports/eval_compare.json with:
     - avg_oracle_score
     - win_rate_v2_over_v1
     - routing_entropy
     - avg_cost/latency proxies

8) TRACE UPGRADE:
   - Emit reports/trace_<runid>.json containing router/swarm/oracle/final sections.

RUN + FINISH:
- Run:
  - pytest -q
  - python scripts/demo_run.py
  - python scripts/bench_run.py
  - python scripts/eval_run.py
  - python scripts/eval_compare.py (if created)
- Update MASTER_HANDOFF.md + FILEMAP.md + CHANGELOG.md with Cycle 2 truth and commands.
- Commit message:
  swarm: cycle-002 router/oracle/swarm/gcel v2 + eval compare
- Print final summary with exact run commands and report paths.
