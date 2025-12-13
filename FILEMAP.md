# FILEMAP — MoAA-Prime

Update this at the end of each phase.
This maps the repo so a new chat window can re-sync instantly.

## Root
- MASTER_HANDOFF.md  -> living handoff / continuity (Phase 1→end)
- FILEMAP.md         -> repo map (this file)
- CHANGELOG.md       -> phase-by-phase changes
- pyproject.toml     -> packaging (src layout)
- src/moaa_prime/... -> library code
- tests/...          -> tests
- scripts/...        -> runnable scripts
- reports/...        -> generated demo/eval outputs (do not rely on being committed)

## Core entrypoints
- src/moaa_prime/core/app.py       -> main app object (MoAAPrime)
- src/moaa_prime/cli/__main__.py   -> `python -m moaa_prime "prompt"` entry

## Agents / Contracts / Router (Phase 2)
- src/moaa_prime/contracts/contract.py
- src/moaa_prime/agents/base.py
- src/moaa_prime/agents/math_agent.py
- src/moaa_prime/agents/code_agent.py
- src/moaa_prime/router/meta_router.py

## Oracle (Phase 3)
- src/moaa_prime/oracle/verifier.py
- src/moaa_prime/oracle/__init__.py

## Swarm (Phase 4+)
- src/moaa_prime/swarm/manager.py
- src/moaa_prime/swarm/__init__.py
- src/moaa_prime/swarm/phase9_stable.py
- src/moaa_prime/cli/phase9_stable_cmd.py

## Memory / E-MRE v1 (Phase 5–6)
- src/moaa_prime/memory/reasoning_bank.py
- src/moaa_prime/memory/*  (AEDMC, SH-COS, GFO, curiosity bump hooks)

## SGM + Fusion (Phase 7)
- src/moaa_prime/sgm/*
- src/moaa_prime/fusion/*
- src/moaa_prime/fusion/mode.py

## SFC (Phase 9)
- src/moaa_prime/sfc/*

## Duality (Phase 10)
- src/moaa_prime/brains/*
- src/moaa_prime/swarm/dual_brain_runner.py

## GCEL (Phase 11)
- src/moaa_prime/evolution/gcel.py

## Eval + Demo (Phase 12)
- src/moaa_prime/eval/runner.py
- src/moaa_prime/eval/report.py
- scripts/eval_run.py
- reports/eval_report.json (generated artifact)
