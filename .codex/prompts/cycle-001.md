You are in repo maddwiz/moaa-prime.

MISSION (Cycle 1: Hard-polish correctness + doc/code alignment):
- Keep changes small + safe + test-backed.
- Create branch: codex/swarm-cycle-001
- After completion: update MASTER_HANDOFF.md + FILEMAP.md + CHANGELOG.md and run python -m pytest -q.

Known repo truths:
- MASTER_HANDOFF says `python -m moaa_prime "prompt"` but current CLI historically used `src/moaa_prime/cli/main.py` subcommands.
- FILEMAP previously referenced `src/moaa_prime/cli/__main__.py` (stale path) and must match real entrypoints.

Spawn these agents and wait for all:
1) Architect:
   - Produce ARCHITECTURE.md (1-2 pages) describing: agents/contracts/router/oracle/swarm/memory/GCEL + optional Ollama wiring.
   - Fix FILEMAP inaccuracies (paths/entrypoints) and propose exact CLI contract.

2) Builder:
   - Implement a canonical CLI entrypoint so `python -m moaa_prime ...` works as documented.
   - Choose one: (A) create src/moaa_prime/__main__.py that dispatches to CLI, OR (B) wire console_script entry point in pyproject.
   - Must preserve existing tests; add/update tests if needed.

3) Docs:
   - If README is empty or stale, create/update a solid README (Quickstart, commands, env vars, demo bundle outputs).
   - Ensure MASTER_HANDOFF + DEMO_README match reality and show correct commands.

4) Tester:
   - Run python -m pytest -q.
   - If CLI behavior changes, add 1-2 tests that lock it down.

5) Eval:
   - Validate scripts/demo_run.py, bench_run.py, eval_run.py, render_report.py write expected JSON outputs under reports/.
   - Ensure reports/ is gitignored.

6) Debugger:
   - Stand by to fix any failures from above.

After all agents finish:
- Merge changes cleanly.
- Run: python -m pytest -q
- Run: python scripts/demo_run.py && python scripts/bench_run.py && python scripts/eval_run.py && python scripts/render_report.py
- Commit with message: "swarm: cycle-001 hard-polish CLI + docs"
- Print final summary: what changed + exact run commands.
