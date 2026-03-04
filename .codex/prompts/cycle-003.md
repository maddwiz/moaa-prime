You are working in repo maddwiz/moaa-prime.

Create and work on branch codex/swarm-cycle-003-autonomous.

MISSION:
Add learning capability to MoAA (Cycle 3).

Deliver:
1. RouterV3 (learned model using traces)
2. Trace recorder producing training data
3. Contract embeddings for agents
4. Pareto swarm selection
5. Router training + eval scripts

Constraints:
- deterministic default behavior
- optional Ollama support
- full file replacements only
- tests must pass
- update MASTER_HANDOFF.md, FILEMAP.md, CHANGELOG.md

Agent roles (run in parallel if available):
- Architect
- RouterBuilder
- SwarmBuilder
- MemoryBuilder
- EvalBuilder
- Tester
- Debugger

Process:
- design architecture
- implement router training pipeline
- implement trace recorder
- implement pareto selector
- run tests and scripts
- commit changes

Required commands before commit:
- pytest -q (or .venv/bin/pytest -q if needed)
- python scripts/demo_run.py
- python scripts/bench_run.py
- python scripts/eval_run.py
- python scripts/eval_compare.py
- python scripts/train_router.py
- python scripts/eval_router.py

Commit message:
swarm: cycle-003 learning system

At the end print:
- what changed
- exact commands run
- report/model/dataset output paths
