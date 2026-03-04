from __future__ import annotations

from dataclasses import dataclass, field, replace
import hashlib
import random
import re
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from moaa_prime.agents.base import BaseAgent


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


_TOKEN_RE = re.compile(r"[a-z0-9_]+")


@dataclass(frozen=True)
class RoutingBudget:
    max_latency_ms: float = 1500.0
    max_cost_tokens: float = 512.0
    latency_weight: float = 0.5
    cost_weight: float = 0.5


@dataclass(frozen=True)
class RouteDecisionV2:
    agent_name: str
    score: float
    reason: str = "router_v2_score"
    rationale: str = ""
    exploration_probability: float = 0.0
    expected_utility: float = 0.0
    selected_by_exploration: bool = False
    components: Dict[str, float] = field(default_factory=dict)


class RouterV2:
    """
    Deterministic Router v2.

    Inputs:
    - prompt/task metadata
    - contracts (through agents)
    - memory hints
    - budget
    - history stats

    Outputs:
    - ranked decisions with rationale, exploration probability, expected utility
    """

    def __init__(
        self,
        agents: Sequence[BaseAgent],
        *,
        seed: int = 0,
        base_exploration: float = 0.08,
        min_exploration: float = 0.02,
        max_exploration: float = 0.35,
    ) -> None:
        self.agents: List[BaseAgent] = list(agents)
        self.seed = int(seed)
        self.base_exploration = float(base_exploration)
        self.min_exploration = float(min_exploration)
        self.max_exploration = float(max_exploration)

    def _call_rng(self, prompt: str, task_metadata: Mapping[str, Any] | None) -> random.Random:
        task_id = ""
        if task_metadata:
            task_id = str(task_metadata.get("task_id") or "")
        raw = f"{self.seed}|{task_id}|{prompt}".encode("utf-8")
        digest = hashlib.sha256(raw).hexdigest()
        rng_seed = int(digest[:16], 16)
        return random.Random(rng_seed)

    def _prompt_tokens(self, prompt: str, task_metadata: Mapping[str, Any] | None) -> set[str]:
        parts = [prompt or ""]
        if task_metadata:
            req = task_metadata.get("required_domains")
            if isinstance(req, list):
                parts.extend(str(x) for x in req)
            objective = task_metadata.get("objective")
            if objective:
                parts.append(str(objective))
        text = " ".join(parts).lower()
        return set(_TOKEN_RE.findall(text))

    def _domain_match(
        self,
        prompt_tokens: set[str],
        domains: Sequence[str],
    ) -> float:
        ds = [d.strip().lower() for d in domains if str(d).strip()]
        if not ds:
            return 0.30

        domain_token_hits = 0
        for d in ds:
            dtoks = set(_TOKEN_RE.findall(d))
            if dtoks and dtoks.intersection(prompt_tokens):
                domain_token_hits += 1

        overlap = domain_token_hits / float(len(ds))

        # Keep legacy-friendly behavior for common signals.
        if "math" in ds and ({"solve", "equation", "algebra", "x"}.intersection(prompt_tokens)):
            overlap = max(overlap, 0.85)
        if "code" in ds and ({"python", "code", "traceback", "error", "function"}.intersection(prompt_tokens)):
            overlap = max(overlap, 0.85)

        return _clamp(overlap, 0.0, 1.0)

    def _memory_alignment(self, agent_name: str, memory_hints: Mapping[str, Any] | None) -> float:
        if not memory_hints:
            return 0.5

        if agent_name in memory_hints:
            try:
                return _clamp(float(memory_hints[agent_name]), 0.0, 1.0)
            except Exception:
                return 0.5

        shared = memory_hints.get("default")
        if shared is not None:
            try:
                return _clamp(float(shared), 0.0, 1.0)
            except Exception:
                return 0.5

        return 0.5

    def _history_success(self, agent_name: str, fallback: float, history_stats: Mapping[str, Any] | None) -> float:
        if not history_stats:
            return _clamp(fallback, 0.0, 1.0)

        row = history_stats.get(agent_name)
        if isinstance(row, Mapping):
            try:
                return _clamp(float(row.get("success_rate", fallback)), 0.0, 1.0)
            except Exception:
                return _clamp(fallback, 0.0, 1.0)

        return _clamp(fallback, 0.0, 1.0)

    def _budget_efficiency(
        self,
        agent_name: str,
        cost_prior: float,
        budget: RoutingBudget,
        history_stats: Mapping[str, Any] | None,
    ) -> float:
        row: Mapping[str, Any] | None = None
        if history_stats:
            maybe = history_stats.get(agent_name)
            if isinstance(maybe, Mapping):
                row = maybe

        pred_latency = 120.0 + (880.0 * _clamp(cost_prior, 0.0, 1.0))
        pred_tokens = 64.0 + (448.0 * _clamp(cost_prior, 0.0, 1.0))

        if row is not None:
            try:
                pred_latency = float(row.get("avg_latency_ms", pred_latency))
            except Exception:
                pass
            try:
                pred_tokens = float(row.get("avg_cost_tokens", pred_tokens))
            except Exception:
                pass

        latency_ratio = _clamp(pred_latency / max(1.0, budget.max_latency_ms), 0.0, 1.0)
        cost_ratio = _clamp(pred_tokens / max(1.0, budget.max_cost_tokens), 0.0, 1.0)

        pressure = (budget.latency_weight * latency_ratio) + (budget.cost_weight * cost_ratio)
        return _clamp(1.0 - pressure, 0.0, 1.0)

    def _score_components(
        self,
        agent: BaseAgent,
        prompt_tokens: set[str],
        memory_hints: Mapping[str, Any] | None,
        budget: RoutingBudget,
        history_stats: Mapping[str, Any] | None,
    ) -> Dict[str, float]:
        c = agent.contract
        name = str(getattr(c, "name", "agent"))

        competence = _clamp(float(getattr(c, "competence", 0.5) or 0.5), 0.0, 1.0)
        reliability = _clamp(float(getattr(c, "reliability", competence) or competence), 0.0, 1.0)
        domains = list(getattr(c, "domains", []) or [])
        cost_prior = _clamp(float(getattr(c, "cost_prior", 0.3) or 0.3), 0.0, 1.0)

        domain_match = self._domain_match(prompt_tokens, domains)
        memory_alignment = self._memory_alignment(name, memory_hints)
        history_success = self._history_success(name, reliability, history_stats)
        budget_efficiency = self._budget_efficiency(name, cost_prior, budget, history_stats)

        utility = (
            (0.35 * competence)
            + (0.20 * reliability)
            + (0.15 * domain_match)
            + (0.10 * memory_alignment)
            + (0.10 * history_success)
            + (0.10 * budget_efficiency)
        )

        return {
            "competence": competence,
            "reliability": reliability,
            "domain_match": domain_match,
            "memory_alignment": memory_alignment,
            "history_success": history_success,
            "budget_efficiency": budget_efficiency,
            "utility": _clamp(utility, 0.0, 1.0),
        }

    def _exploration_probability(self, ranked_components: List[Dict[str, float]]) -> float:
        if not ranked_components:
            return self.min_exploration

        top = ranked_components[0]["utility"]
        second = ranked_components[1]["utility"] if len(ranked_components) > 1 else top

        margin = _clamp(top - second, 0.0, 1.0)
        budget_pressure = 1.0 - _clamp(ranked_components[0]["budget_efficiency"], 0.0, 1.0)

        eps = self.base_exploration + (0.22 * (1.0 - margin)) + (0.18 * budget_pressure)
        return _clamp(eps, self.min_exploration, self.max_exploration)

    def _rationale(self, components: Dict[str, float]) -> str:
        ranked = sorted(
            (
                ("competence", components["competence"]),
                ("reliability", components["reliability"]),
                ("domain_match", components["domain_match"]),
                ("memory_alignment", components["memory_alignment"]),
                ("history_success", components["history_success"]),
                ("budget_efficiency", components["budget_efficiency"]),
            ),
            key=lambda kv: kv[1],
            reverse=True,
        )
        top2 = ", ".join(f"{k}={v:.2f}" for k, v in ranked[:2])
        return f"utility={components['utility']:.3f}; {top2}"

    def route_top_k(
        self,
        prompt: str,
        k: int = 2,
        *,
        task_metadata: Optional[Mapping[str, Any]] = None,
        memory_hints: Optional[Mapping[str, Any]] = None,
        budget: Optional[RoutingBudget | Mapping[str, Any]] = None,
        history_stats: Optional[Mapping[str, Any]] = None,
    ) -> Tuple[List[BaseAgent], List[RouteDecisionV2]]:
        if k <= 0:
            k = 1
        k = min(k, len(self.agents))

        if budget is None:
            budget_obj = RoutingBudget()
        elif isinstance(budget, RoutingBudget):
            budget_obj = budget
        else:
            budget_obj = RoutingBudget(
                max_latency_ms=float(budget.get("max_latency_ms", 1500.0)),
                max_cost_tokens=float(budget.get("max_cost_tokens", 512.0)),
                latency_weight=float(budget.get("latency_weight", 0.5)),
                cost_weight=float(budget.get("cost_weight", 0.5)),
            )

        prompt_tokens = self._prompt_tokens(prompt or "", task_metadata)

        scored: List[Tuple[float, str, BaseAgent, Dict[str, float]]] = []
        for agent in self.agents:
            comps = self._score_components(agent, prompt_tokens, memory_hints, budget_obj, history_stats)
            agent_name = str(getattr(agent.contract, "name", "agent"))
            scored.append((float(comps["utility"]), agent_name, agent, comps))

        scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
        eps = self._exploration_probability([row[3] for row in scored])

        agents: List[BaseAgent] = []
        decisions: List[RouteDecisionV2] = []

        for utility, _name, agent, comps in scored[:k]:
            agents.append(agent)
            decisions.append(
                RouteDecisionV2(
                    agent_name=str(getattr(agent.contract, "name", "agent")),
                    score=float(utility),
                    reason="router_v2_score",
                    rationale=self._rationale(comps),
                    exploration_probability=float(eps),
                    expected_utility=float(utility),
                    selected_by_exploration=False,
                    components={k: float(v) for k, v in comps.items()},
                )
            )

        return agents, decisions

    def route(
        self,
        prompt: str,
        *,
        task_metadata: Optional[Mapping[str, Any]] = None,
        memory_hints: Optional[Mapping[str, Any]] = None,
        budget: Optional[RoutingBudget | Mapping[str, Any]] = None,
        history_stats: Optional[Mapping[str, Any]] = None,
        top_k: int = 2,
    ) -> Tuple[BaseAgent, RouteDecisionV2]:
        k = min(max(1, int(top_k)), len(self.agents))
        agents, decisions = self.route_top_k(
            prompt,
            k=max(2, k) if len(self.agents) > 1 else 1,
            task_metadata=task_metadata,
            memory_hints=memory_hints,
            budget=budget,
            history_stats=history_stats,
        )

        if not agents:
            raise ValueError("RouterV2 requires at least one agent")

        best = decisions[0]
        eps = float(best.exploration_probability)
        rng = self._call_rng(prompt or "", task_metadata)

        picked_idx = 0
        picked_by_exploration = False
        if len(agents) > 1 and rng.random() < eps:
            picked_idx = 1 + rng.randrange(len(agents) - 1)
            picked_by_exploration = True

        chosen_agent = agents[picked_idx]
        chosen_decision = replace(decisions[picked_idx], selected_by_exploration=picked_by_exploration)
        return chosen_agent, chosen_decision
