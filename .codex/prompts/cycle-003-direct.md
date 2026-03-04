You are working in repo maddwiz/moaa-prime on branch codex/swarm-cycle-003-autonomous.

MISSION:
Implement Cycle 3 learning system end-to-end.

REQUIRED DELIVERABLES:
1) RouterV3 (learned model using traces)
2) Trace recorder producing training data
3) Contract embeddings for agents
4) Pareto swarm selection
5) Router training + eval scripts

HARD EXECUTION RULES:
- Implement directly in this agent.
- Do NOT call spawn_agent/send_input/wait tools.
- Do NOT run no-op shell commands (`true`, `echo test`, `pwd` loops).
- Make concrete file edits immediately and proceed to completion.

CONSTRAINTS:
- deterministic default behavior
- optional Ollama support remains available
- full file replacements only when editing files
- tests must pass
- update MASTER_HANDOFF.md, FILEMAP.md, CHANGELOG.md

REQUIRED VALIDATION COMMANDS:
- pytest -q (or .venv/bin/pytest -q)
- python scripts/demo_run.py
- python scripts/bench_run.py
- python scripts/eval_run.py
- python scripts/eval_compare.py
- python scripts/train_router.py
- python scripts/eval_router.py

COMMIT:
- commit message: swarm: cycle-003 learning system

FINAL OUTPUT MUST INCLUDE:
- files changed
- exact commands run
- report/model/dataset output paths
