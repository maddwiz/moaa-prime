# Architecture Cycle 2 — Real MoAA Lift

## Goal
Cycle 2 introduces measurable, deterministic v2 decision logic while preserving v1 behavior for A/B comparison.

A/B switch:
- `v1`: legacy `MetaRouter` + `OracleVerifier` + legacy swarm/GCEL behavior
- `v2`: `RouterV2` + `OracleV2` + `SwarmManager(mode="v2")` + `GCELV2`

Mode can be selected by:
- `MoAAPrime(mode="v1"|"v2")`
- `MOAA_AB_MODE=v1|v2`

## Data Flow
1. Prompt + task context enter `MoAAPrime.run_once(...)` or `MoAAPrime.run_swarm(...)`.
2. Mode resolver selects v1 or v2 components.
3. `RouterV2` scores all candidate agents using contracts + context + budget/history signals.
4. `SwarmV2` generates `N = rounds * top_k` candidates.
5. `OracleV2` scores each candidate with weighted rubric components in `[0,1]`.
6. Swarm picks best candidate, computes confidence, and emits structured trace.
7. Optional `GCELV2` proposes bounded contract mutations and accepts only when eval score improves.

## RouterV2 Interface
`src/moaa_prime/router/router_v2.py`

Primary API:
- `route(prompt, task_metadata=None, memory_hints=None, budget=None, history_stats=None, top_k=2) -> (agent, RouteDecision)`
- `route_top_k(prompt, k=2, task_metadata=None, memory_hints=None, budget=None, history_stats=None) -> (agents, decisions)`

Inputs:
- prompt/task metadata
- per-agent contracts
- memory hints
- budget constraints
- historical success/latency/cost stats

Output decision fields (per ranked agent):
- `score`
- `expected_utility`
- `exploration_probability`
- `selected_by_exploration`
- `components` (scoring breakdown)
- `rationale`

### RouterV2 Score Formula
All components are clamped to `[0,1]`.

`utility =`
- `0.35 * competence`
- `+ 0.20 * reliability`
- `+ 0.15 * domain_match`
- `+ 0.10 * memory_alignment`
- `+ 0.10 * history_success`
- `+ 0.10 * budget_efficiency`

Exploration probability (`epsilon-greedy`) uses margin + budget pressure:
- `margin = top_utility - second_utility`
- `budget_pressure = 1 - best_budget_efficiency`
- `eps = clamp(base_exploration + 0.22*(1-margin) + 0.18*budget_pressure, min_exploration, max_exploration)`

Determinism:
- seeded hash-based PRNG per call (`seed + prompt + task metadata`).

## OracleV2 Interface
`src/moaa_prime/oracle/verifier.py`

Primary API:
- `verdict(prompt, answer) -> OracleVerdict`
- `score(prompt, answer) -> float`
- `consistency_check(prompt, answer, repeats=5) -> {mean, variance, max_delta, stable}`

Rubric config:
- JSON/YAML file path supported (`rubric_path`)
- default bundled rubric file: `src/moaa_prime/oracle/rubric_v2.yaml`

### OracleV2 Rubric Components
Weighted score in `[0,1]`:
- correctness proxy
- coherence
- constraint adherence
- safety/overreach
- grounding

Default weights:
- correctness proxy: `0.34`
- coherence: `0.20`
- constraint adherence: `0.18`
- safety/overreach: `0.16`
- grounding: `0.12`

Final score:
- weighted sum of components
- clamped to `[0,1]`

## SwarmV2 Interface
`src/moaa_prime/swarm/manager.py`

Primary API (backward compatible):
- `run(prompt, task_id="default", rounds=2, top_k=2, mode=None, ...) -> {best, candidates, ...}`

V2 behavior:
- generate `N` candidates across rounds/top-k routes
- score each candidate through `OracleV2`
- optional top-2 cross-check round (`cross_check=True`; default stubbed `False`)
- choose best by oracle score, compute confidence from margin/dispersion
- include trace payload

Trace schema (`reports/trace_<runid>.json`):
- `router`: ranked decisions + exploration metadata
- `swarm`: generation params/candidate count/cross-check result
- `oracle`: per-candidate scores + component blocks
- `final`: chosen candidate + confidence + score

## GCELV2 Interface
`src/moaa_prime/evolution/gcel.py`

New contract priors:
- `reliability` (0..1)
- `cost_prior` (0..1, lower is cheaper)

Primary API:
- `GCELV2.evolve(contracts, metrics, evaluator=None) -> GCELV2Outcome`

Fitness aggregation:
- `fitness = 0.45*oracle_score + 0.35*eval_success + 0.20*budget_efficiency`

Mutation policy:
- small bounded deltas on competence/reliability/cost_prior
- deterministic with seed

Acceptance gate:
- candidate contracts are accepted only when evaluator score improves by `min_improvement`
- otherwise baseline contracts are kept

## Eval Compare Output
`python scripts/eval_compare.py` writes `reports/eval_compare.json` with:
- `avg_oracle_score`
- `win_rate_v2_over_v1`
- `routing_entropy`
- `avg_cost_proxy`
- `avg_latency_proxy`

Run uses same seed + same case slice for v1 and v2.
