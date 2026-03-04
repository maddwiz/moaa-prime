# MoAA-Prime Architecture

## System Overview

MoAA-Prime is a deterministic, test-first multi-agent orchestration prototype.  
The composition root is `MoAAPrime` in `src/moaa_prime/core/app.py`, which wires:

1. agent contracts (`Contract`)
2. specialist agents (`MathAgent`, `CodeAgent`)
3. routing (`MetaRouter`)
4. verification (`OracleVerifier`)
5. swarm deliberation (`SwarmManager`)
6. shared memory (`ReasoningBank`)
7. contract evolution (`GCEL`)

Primary control flow:

1. A prompt enters via CLI or Python call (`run_once` / `run_swarm`).
2. Router picks one agent (`run_once`) or top-k agents (`run_swarm`).
3. Agent handles prompt through the configured LLM client and memory hooks.
4. Oracle scores the output and adds a reasoned verification block.
5. Optional swarm/SFC loops add multi-candidate deliberation and early-stop gating.
6. Optional GCEL updates contract priors from fitness signals.

## Composition Root (`src/moaa_prime/core/app.py`)

`MoAAPrime.__init__` currently instantiates:

- `ReasoningBank()` as global memory store
- two `Contract`s (`math-agent`, `code-agent`)
- `MathAgent` and `CodeAgent` bound to the shared bank
- `MetaRouter([math, code])`
- `OracleVerifier()`
- `SwarmManager(router, oracle)`
- `GCEL(mutation_step=0.04, elite_frac=0.50, seed=0)`

Public app methods:

- `hello() -> str`
- `run_once(prompt, task_id="default") -> {"decision","result","oracle"}`
- `run_swarm(prompt, task_id="default", rounds=3, top_k=2) -> {"best","candidates"}`
- `evolve_contracts(fitness) -> {"before","after"}`

## Contracts by Subsystem

### 1) Agents

Files:

- `src/moaa_prime/agents/base.py`
- `src/moaa_prime/agents/math_agent.py`
- `src/moaa_prime/agents/code_agent.py`

Behavioral contract:

- `BaseAgent.handle(prompt, task_id)` returns `AgentResult(agent_name, text, meta)`.
- `meta` includes model identity and memory diagnostics (`local_hits`, `bank_hits`, snippets, write method).
- Concrete agent classes are thin wrappers over `BaseAgent`; differentiation is currently via contract priors and router heuristics.

### 2) Contracts

File: `src/moaa_prime/contracts/contract.py`

`Contract` is an immutable dataclass with:

- `name`
- `domains[]`
- `tools[]`
- `modalities{}`
- `competence` (expected range 0..1, GCEL clamps to 0.05..0.99)

This object is the shared boundary for routing and evolution.

### 3) Router

File: `src/moaa_prime/router/meta_router.py`

Contract:

- `route(prompt) -> (agent, RouteDecision)`
- `route_top_k(prompt, k) -> (agents, decisions)` sorted high to low score

Scoring is deterministic: base competence plus small domain-keyword bumps.  
`RouteDecision` exposes `agent_name`, `score`, `reason="router_score"`.

### 4) Oracle

File: `src/moaa_prime/oracle/verifier.py`

Contract:

- `verdict(prompt, answer) -> OracleVerdict(score, reason, meta)`
- `score(prompt, answer) -> float` clamped to `[0,1]`

`run_once` and swarm candidates always surface an `oracle` block for downstream evaluation.

### 5) Swarm

Files:

- `src/moaa_prime/swarm/manager.py`
- `src/moaa_prime/swarm/phase9_stable.py`
- `src/moaa_prime/sfc/controller.py`

`SwarmManager` supports two construction modes:

- router-driven (`SwarmManager(MetaRouter, oracle)`)
- direct agent list (`SwarmManager([agents...], oracle)`)

Canonical swarm API:

- `run(prompt, task_id, rounds, top_k) -> {"best","candidates"}`
- picks `best` by max oracle score
- candidate records include `agent`, `text`, `meta`, `oracle`

Phase 9 stable path (`StableSwarmRunner`) wraps swarm calls with SFC gating and returns `stopped_early` plus `sfc_value`.

### 6) Memory

Files:

- `src/moaa_prime/memory/reasoning_bank.py`
- `src/moaa_prime/memory/episodic_lane.py`
- `src/moaa_prime/memory/emre.py`

`ReasoningBank` provides:

- backward-compatible write API (`write`, `add`, `append` fallbacks from `BaseAgent`)
- task-scoped recall with similarity ranking
- `kl_like` novelty signal
- SH-COS text summary (`global_text`)

`EpisodicLane` adds E-MRE-inspired mechanics:

- entropy proxy -> adaptive Markov order
- curiosity bump (`kl_like`)
- SH-COS layered text summaries
- GFO pruning when working memory exceeds threshold

### 7) GCEL (Genetic Contract Evolution Loop)

File: `src/moaa_prime/evolution/gcel.py`

Contract:

- `GCEL.evolve(contracts, fitness) -> List[Contract]`
- preserves list length, order, and original names
- clamps competence to `[0.05, 0.99]`
- combines elite retention, crossover, and bounded mutation

`MoAAPrime.evolve_contracts` applies evolved contracts back to live agents and emits before/after snapshots.

## Optional Ollama Wiring

Files:

- `src/moaa_prime/llm/factory.py`
- `src/moaa_prime/llm/client.py`
- `src/moaa_prime/llm/ollama_client.py`

LLM selection is environment-driven:

- default: `StubLLMClient` (`MOAA_LLM_PROVIDER` unset or `stub`)
- Ollama: set `MOAA_LLM_PROVIDER=ollama`
- optional overrides: `MOAA_OLLAMA_HOST`, `MOAA_OLLAMA_MODEL`

Every `BaseAgent` calls `make_llm_from_env()`, so provider wiring is centralized and test behavior remains deterministic by default.
