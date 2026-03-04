You are working in repo `maddwiz/moaa-prime`.

Objective:
Finish MoAA-Prime by implementing and hardening the roadmap in `ROADMAP.md` (PR-0 through PR-5 first), proving improvements with deterministic eval artifacts.

Execution policy:
- Use Codex multi-agent mode for implementation work.
- Complete one PR-sized roadmap item per cycle with tests + reports + docs.
- Keep API contracts stable; no silent schema drift.
- Keep changes safe, incremental, and test-backed.
- Do not stop at planning; ship concrete code each cycle.

Roadmap priority (must follow in order):
1. PR-0: repo hygiene + contract freeze (`CONTRACTS.md` + compatibility tests).
2. PR-1: tool-first policy layer for math/code correctness.
3. PR-2: deterministic code sandbox verify + repair loop integration.
4. PR-3: router intent-first stabilizer + route trace metadata.
5. PR-4: gated dual-brain best-of selector (no blind dual mode).
6. PR-5: eval matrix comparative ablations with machine-readable summary.

Non-negotiables:
- Preserve API shapes documented in `CONTRACTS.md`.
- Keep tests green at all times.
- Keep generated outputs gitignored.
- Optional Ollama support must remain intact.

Required cycle outputs:
- code changes
- tests and/or compatibility assertions
- updated docs (`MASTER_HANDOFF.md`, `FILEMAP.md`, `CHANGELOG.md`)
- one commit with a clear message

Required validation before finishing a cycle:
- `pytest -q`
- run relevant scripts for touched subsystems
- when touching eval stack: run `scripts/eval_matrix.py`

Definition of done:
- determined by `.codex/done_criteria.json` and enforced by `scripts/check_done.py`.
- do not claim completion manually; only the done-check gate can finalize.
