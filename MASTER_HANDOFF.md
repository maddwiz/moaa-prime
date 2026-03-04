# MASTER_HANDOFF — MoAA-Prime

Owner: Desmond  
Local path: `~/moaa-prime`

## Golden Rules

- Keep changes small, test-backed, and reversible.
- Update `MASTER_HANDOFF.md`, `FILEMAP.md`, and `CHANGELOG.md` when behavior changes.
- Treat `reports/` as generated output.

## What MoAA-Prime Is (Current)

MoAA-Prime is a Mixture of Adaptive Agents prototype with:

- contract-based specialist agents
- meta-routing with decision metadata
- oracle scoring
- swarm deliberation
- memory (episodic + ReasoningBank + E-MRE hooks)
- SGM / energy fusion scaffolding
- SFC stability gates
- dual-brain runner scaffolding
- GCEL contract evolution
- demo, benchmark, eval, and report scripts
- optional Ollama provider wiring

## Current Truth Snapshot

- tests run via `python -m pytest -q`
- module CLI works via `python -m moaa_prime ...`
- demo bundle scripts write JSON files under `reports/`

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e .
```

## Codex Swarm Setup

- Project multi-agent config: `.codex/config.toml`
- Role files: `.codex/agents/*.toml`
- Expected local Codex feature flag: `~/.codex/config.toml` with `features.multi_agent = true`

## Run

### Tests

```bash
python -m pytest -q
```

### CLI

Shorthand route:

```bash
python -m moaa_prime "Solve: 2x + 3 = 7. Return only x."
```

Explicit commands:

```bash
python -m moaa_prime hello
python -m moaa_prime route "Write Python: function add(a,b) returns a+b"
python -m moaa_prime swarm "Explain why 1/0 is undefined."
```

### Demo Bundle

```bash
python scripts/demo_run.py
python scripts/bench_run.py
python scripts/eval_run.py
python scripts/render_report.py
```

Expected outputs:

- `reports/demo_run.json`
- `reports/bench.json`
- `reports/eval_report.json`
- `reports/final_report.json`

## Ollama Wiring (Optional)

```bash
export MOAA_LLM_PROVIDER=ollama
export MOAA_OLLAMA_HOST="http://127.0.0.1:11434"
export MOAA_OLLAMA_MODEL="llama3.1:8b-instruct-q4_K_M"
```

Sanity check:

```bash
curl -s http://127.0.0.1:11434/api/tags | head
```

## Phase Status

- Phase 1: Packaging + smoke
- Phase 2: Agents + contracts + router
- Phase 3: Oracle
- Phase 4: Swarm
- Phase 5: Memory v1
- Phase 6: E-MRE hooks
- Phase 7: SGM + energy fusion scaffolding
- Phase 8: Consolidation
- Phase 9: SFC hooks
- Phase 10: Dual-brain runner hooks
- Phase 11: GCEL
- Phase 12: Demo + bench + eval scripts
- Cycle 001: CLI module entrypoint + doc/code alignment

## Repo Hygiene Notes

- Keep `reports/` out of source control.
- Use branch-per-cycle and merge via tested commits.
