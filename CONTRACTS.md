# CONTRACTS (PR-0 Freeze)

Scope: Stable output and interface contracts for:
- `MoAAPrime.run_once(...).decision`
- `MoAAPrime.run_swarm(...)`
- `BaseAgent.handle(...)` / `AgentResult`
- Agent memory meta payload

Source of truth for this freeze:
- `src/moaa_prime/core/app.py`
- `src/moaa_prime/swarm/manager.py`
- `src/moaa_prime/agents/base.py`

## 1) Router output shape (`MoAAPrime.run_once(...).decision`)

`run_once(...)` returns a top-level `decision` object with these required keys and types:

```json
{
  "agent": "string",
  "score": 0.0,
  "reason": "string",
  "rationale": "string",
  "exploration_probability": 0.0,
  "expected_utility": 0.0,
  "selected_by_exploration": false,
  "components": {}
}
```

Required keys:
- `agent: str`
- `score: float`
- `reason: str`
- `rationale: str`
- `exploration_probability: float`
- `expected_utility: float`
- `selected_by_exploration: bool`
- `components: dict`

Notes:
- Values are normalized with defaults in `run_once(...)` (missing router attributes are backfilled).
- `components` is implementation-defined but must remain a dictionary.
- Additive debug field:
  - `route_trace: dict` may be emitted at top level with router intent metadata (`intent`, `matched_features`, `chosen_agent`, etc.).

## 2) Swarm output shape (`MoAAPrime.run_swarm(...)`)

`run_swarm(...)` returns the `SwarmManager.run(...)` payload plus app-level trace paths.

Required top-level keys:
- `mode: str` (`"v1" | "v2" | "v3"`)
- `best: dict`
- `candidates: list[dict]`
- `confidence: float`
- `trace: dict`
- `avg_latency_proxy: float`
- `avg_cost_proxy: float`
- `learning_trace_path: str`
- `router_dataset_path: str`

Conditional top-level key:
- `trace_path: str` is present only when `run_swarm(..., run_id=...)` is provided.

### 2.1 `best` and `candidates[*]` item shape

Each candidate object (and `best`) uses this shape:

```json
{
  "agent": "string",
  "text": "string",
  "meta": {},
  "oracle": {
    "score": 0.0,
    "reason": "string",
    "meta": {}
  },
  "round": 1,
  "rank": 0,
  "latency_proxy": 0.0,
  "cost_proxy": 0.0,
  "confidence_proxy": 0.0
}
```

Required keys:
- `agent: str`
- `text: str`
- `meta: dict`
- `oracle: dict` with required `score: float`, `reason: str`, `meta: dict`
- `round: int`
- `rank: int`
- `latency_proxy: float`
- `cost_proxy: float`
- `confidence_proxy: float`

Additive candidate key currently used:
- `critique: str` may be attached during v3 cross-critique.

### 2.2 `trace` shape

`trace` contains required blocks:
- `router: dict`
- `swarm: dict`
- `oracle: dict`
- `final: dict`

`trace.router` required keys:
- `mode: str`
- `ranked: list[dict]`
- `exploration_probability: float`

Additive router-trace metadata (PR-3 intent trace, optional but stable when present):
- `intent: str` (`"math" | "code" | "general"`)
- `intent_scores: dict[str, float]`
- `intent_confidence: float`
- `matched_features: list[str]`
- `chosen_agent: str`
- `alternatives: list[dict]` with additive fields such as `agent`, `score`, `reason`, `rationale`
- `ranking_rationale: str`

Each `trace.router.ranked[*]` required keys:
- `agent: str`
- `score: float`
- `expected_utility: float`
- `exploration_probability: float`
- `selected_by_exploration: bool`
- `reason: str`
- `rationale: str`
- `components: dict`

`trace.swarm` required keys:
- `mode: str`
- `rounds: int`
- `top_k: int`
- `num_candidates: int`
- `cross_check: dict`
- `pareto: dict`
- `budget_mode: str`

Additive swarm-trace metadata (PR-4 dual gate, optional):
- `dual_gate: dict` with additive debug fields such as:
  - `enabled: bool`
  - `triggered: bool`
  - `reasons: list[str]`
  - `selector: dict` (for example `winner_source`, `rule`)

`trace.oracle` required keys:
- `mode: str`
- `scores: list[dict]` where each item has required `agent: str`, `score: float`, `reason: str`, `components: dict`

`trace.final` required keys:
- `agent: str`
- `score: float`
- `confidence: float`
- `budget_mode: str`

## 3) Agent interface contract (`BaseAgent.handle` / `AgentResult`)

`AgentResult` dataclass shape:

```json
{
  "agent_name": "string",
  "text": "string",
  "meta": {}
}
```

Field contract:
- `agent_name: str`
- `text: str`
- `meta: dict | null` (optional at type level)

`BaseAgent.handle` method contract:
- Signature: `handle(prompt: str, task_id: str = "default") -> AgentResult`
- `agent_name` must identify the handling agent (base implementation uses `self.contract.name`).
- `text` must contain the generated response body.
- `meta` may include extra keys; base implementation includes model + memory metadata.

## 4) Memory Meta Contract

When produced by `BaseAgent.handle(...)`, `AgentResult.meta` includes `memory` with required keys:
- `local_hits: int`
- `bank_hits: int`

Current base memory payload keys:
- `local_hits: int`
- `local_snippets: list`
- `bank_hits: int`
- `bank_snippets: list`
- `write: dict`
- `method: str | null`
- `task_id: str`

`local_hits` and `bank_hits` are mandatory in this freeze and must remain numeric counts.

## 5) App Method Signature Compatibility

`MoAAPrime` public method signatures are frozen for required positional arguments:

- `run_once(prompt, task_id="default", *, ...)`
  - required positional/positional-or-keyword:
    - `prompt`
    - `task_id` (default `"default"`)
  - additive parameters must be keyword-only.

- `run_swarm(prompt, task_id="default", rounds=3, top_k=2, *, ...)`
  - required positional/positional-or-keyword:
    - `prompt`
    - `task_id` (default `"default"`)
    - `rounds` (default `3`)
    - `top_k` (default `2`)
  - additive parameters must be keyword-only.

## Compatibility Policy

- Required keys listed above are stable.
- Additive fields are allowed at any object level.
- Additive fields may be present or absent; consumers must not depend on additive fields as required.
- Silent removals of required keys are not allowed.
- Silent type changes for required keys are not allowed.
- Any removal or type change requires an explicit contract/version update.
