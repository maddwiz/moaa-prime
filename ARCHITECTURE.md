# MoAA-Prime Architecture

## System Overview

MoAA-Prime is a layered orchestration system around specialist agents. The central façade is `MoAAPrime` in `src/moaa_prime/core/app.py`, which wires together routing, verification, swarm, memory, and contract evolution.

High-level flow:

1. Input prompt arrives at app entrypoint.
2. Router chooses an agent (or candidates in swarm mode).
3. Agent executes and returns structured output.
4. Oracle scores output quality/truthfulness.
5. Memory hooks store/read useful traces.
6. Optional swarm and evolution paths refine outcomes over time.

## Core Contracts

### 1) Agent Contract

`src/moaa_prime/contracts/contract.py` defines per-agent policy:

- identity (`name`)
- domain affinity (`domains`)
- tool affordances (`tools`)
- competence score (bounded numeric signal)

The contract is a stable boundary between router decisions and execution capability.

### 2) Router Contract

`src/moaa_prime/router/meta_router.py` maps prompt signals to a target agent and emits a decision object (`agent_name`, `score`, `reason`). This decision metadata is preserved in top-level outputs for traceability.

### 3) Oracle Contract

`src/moaa_prime/oracle/verifier.py` computes a verification verdict for generated text. `MoAAPrime.run_once` and swarm paths embed oracle results in a dedicated `oracle` block so downstream evaluators can inspect confidence and reasoning.

### 4) Swarm Contract

`src/moaa_prime/swarm/manager.py` runs multi-candidate deliberation. It coordinates rounds/top-k behavior and selects a best candidate based on scoring/stability signals. Stable command helpers remain available in `src/moaa_prime/cli/phase9_stable_cmd.py`.

### 5) Memory Contract

`src/moaa_prime/memory/` provides:

- per-agent episodic lanes
- shared `ReasoningBank`
- E-MRE hooks (AEDMC, SH-COS, GFO, curiosity hooks)

Agent outputs include memory metadata so tests and evaluators can confirm recall/write behavior.

### 6) Evolution Contract (GCEL)

`src/moaa_prime/evolution/gcel.py` mutates and selects contracts from fitness signals. `MoAAPrime.evolve_contracts` applies evolved contracts back to live agents and returns before/after snapshots.

## Runtime Modes

### `run_once`

- single routed execution
- oracle verification
- memory metadata surfaced in result

### `run_swarm`

- multi-candidate execution
- candidate ranking + stability controls

### Eval/Bench/Demo Scripts

Located in `scripts/`:

- `demo_run.py` exercises once + swarm + evolve paths
- `bench_run.py` records latency
- `eval_run.py` executes test cases via `EvalRunner`
- `render_report.py` aggregates run artifacts

All outputs write to `reports/`.

## CLI and Entry Points

Canonical module entrypoint:

- `src/moaa_prime/__main__.py`
- run as `python -m moaa_prime ...`

Parser behavior in `src/moaa_prime/cli/main.py`:

- shorthand prompt routes once: `python -m moaa_prime "prompt"`
- explicit commands: `hello`, `route`, `swarm`

Installed console script:

- `moaa-prime` from `[project.scripts]` in `pyproject.toml`

## Optional Ollama Provider

`src/moaa_prime/llm/factory.py` chooses provider based on env vars:

- default stub client (deterministic local behavior)
- Ollama client when `MOAA_LLM_PROVIDER=ollama`

This keeps test behavior stable by default while allowing real model execution in demo/bench runs.
