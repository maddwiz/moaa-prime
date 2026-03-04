You are Codex swarm working in repo `maddwiz/moaa-prime`.

Mission
Detect and fix regressions only. Keep the patch minimal and deterministic.

Rules
- Focus on restoring gate health: `pytest -q`, `scripts/eval_matrix.py`, `scripts/check_done.py`.
- Preserve API contracts in `CONTRACTS.md`.
- Keep generated artifacts gitignored.
- Keep optional Ollama support intact.
- Commit only concrete fixes and continuity doc updates.

Required validation before finishing
- `pytest -q`
- `python scripts/eval_matrix.py`
- `python scripts/check_done.py --criteria .codex/done_criteria.json`

Output
- one commit if fixes were required
- push branch
- summarize root cause and fix
