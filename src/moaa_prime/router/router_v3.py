from __future__ import annotations

from dataclasses import dataclass, field, replace
import hashlib
import json
import math
from pathlib import Path
import random
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from moaa_prime.agents.base import BaseAgent
from moaa_prime.contracts import Contract

from .embeddings import contract_embedding, cosine_similarity, task_embedding
from .router_v2 import RoutingBudget


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _sigmoid(x: float) -> float:
    z = _clamp(float(x), -50.0, 50.0)
    return 1.0 / (1.0 + math.exp(-z))


FEATURE_NAMES: list[str] = [
    "similarity",
    "competence",
    "reliability",
    "success_rate",
    "oracle_history",
    "latency_efficiency",
    "cost_efficiency",
    "memory_alignment",
]


BUDGET_PROFILES: dict[str, dict[str, float]] = {
    "cheap": {
        "quality_weight": 0.45,
        "cost_weight": 0.35,
        "latency_weight": 0.20,
    },
    "balanced": {
        "quality_weight": 0.65,
        "cost_weight": 0.20,
        "latency_weight": 0.15,
    },
    "max_quality": {
        "quality_weight": 0.85,
        "cost_weight": 0.08,
        "latency_weight": 0.07,
    },
}


@dataclass(frozen=True)
class RouteDecisionV3:
    agent_name: str
    score: float
    reason: str = "router_v3_learned"
    rationale: str = ""
    exploration_probability: float = 0.0
    expected_utility: float = 0.0
    selected_by_exploration: bool = False
    components: Dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class RouterV3Model:
    feature_names: List[str] = field(default_factory=lambda: list(FEATURE_NAMES))
    weights: Dict[str, float] = field(
        default_factory=lambda: {
            "similarity": 1.80,
            "competence": 0.65,
            "reliability": 0.75,
            "success_rate": 0.90,
            "oracle_history": 0.85,
            "latency_efficiency": 0.55,
            "cost_efficiency": 0.50,
            "memory_alignment": 0.35,
        }
    )
    bias: float = -1.25
    calibration_scale: float = 1.0
    calibration_bias: float = 0.0
    seed: int = 0
    version: str = "router_v3"

    def predict_logit(self, features: Mapping[str, float]) -> float:
        z = float(self.bias)
        for name in self.feature_names:
            z += float(self.weights.get(name, 0.0)) * float(features.get(name, 0.0))
        return z

    def calibrate_logit(self, logit: float) -> float:
        return (float(self.calibration_scale) * float(logit)) + float(self.calibration_bias)

    def predict_expected_success(self, features: Mapping[str, float]) -> float:
        return _sigmoid(self.calibrate_logit(self.predict_logit(features)))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "seed": int(self.seed),
            "bias": float(self.bias),
            "calibration_scale": float(self.calibration_scale),
            "calibration_bias": float(self.calibration_bias),
            "feature_names": list(self.feature_names),
            "weights": {k: float(v) for k, v in self.weights.items()},
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "RouterV3Model":
        feature_names = [str(x) for x in data.get("feature_names", FEATURE_NAMES)]
        raw_weights = data.get("weights", {}) or {}
        weights = {str(k): float(v) for k, v in raw_weights.items()}
        for key in feature_names:
            weights.setdefault(key, 0.0)

        calibration_scale = 1.0
        calibration_bias = 0.0
        raw_calibration = data.get("calibration", {})
        if isinstance(raw_calibration, Mapping):
            calibration_scale = float(raw_calibration.get("scale", data.get("calibration_scale", 1.0)))
            calibration_bias = float(raw_calibration.get("bias", data.get("calibration_bias", 0.0)))
        else:
            calibration_scale = float(data.get("calibration_scale", 1.0))
            calibration_bias = float(data.get("calibration_bias", 0.0))

        return cls(
            feature_names=feature_names,
            weights=weights,
            bias=float(data.get("bias", -1.25)),
            calibration_scale=calibration_scale,
            calibration_bias=calibration_bias,
            seed=int(data.get("seed", 0)),
            version=str(data.get("version", "router_v3")),
        )


def load_router_v3_model(path: str | Path, *, seed: int = 0) -> RouterV3Model:
    p = Path(path)
    if not p.exists():
        return RouterV3Model(seed=int(seed))

    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            return RouterV3Model.from_dict(payload)
    except Exception:
        pass
    return RouterV3Model(seed=int(seed))


def save_router_v3_model(path: str | Path, model: RouterV3Model) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(model.to_dict(), indent=2, sort_keys=True), encoding="utf-8")


def build_router_v3_features(
    prompt: str,
    contract: Contract,
    *,
    history_row: Mapping[str, Any] | None = None,
    memory_alignment: float = 0.5,
    budget: RoutingBudget | None = None,
    embedding_dim: int = 24,
    seed: int = 0,
) -> Dict[str, float]:
    history_row = history_row or {}
    budget = budget or RoutingBudget()

    t_emb = task_embedding(prompt, dim=embedding_dim, seed=seed)

    c_emb = list(contract.embedding or [])
    if not c_emb:
        c_emb = contract_embedding(contract, dim=embedding_dim, seed=seed)

    similarity = _clamp((cosine_similarity(t_emb, c_emb) + 1.0) / 2.0, 0.0, 1.0)
    competence = _clamp(float(contract.competence), 0.0, 1.0)
    reliability = _clamp(float(contract.reliability), 0.0, 1.0)

    success_rate = _clamp(float(history_row.get("success_rate", reliability)), 0.0, 1.0)
    oracle_history = _clamp(float(history_row.get("avg_oracle_score", success_rate)), 0.0, 1.0)

    pred_latency = float(history_row.get("avg_latency_ms", 120.0 + (860.0 * float(contract.cost_prior))))
    pred_cost = float(history_row.get("avg_cost_tokens", 64.0 + (460.0 * float(contract.cost_prior))))

    latency_efficiency = _clamp(1.0 - (pred_latency / max(1.0, budget.max_latency_ms)), 0.0, 1.0)
    cost_efficiency = _clamp(1.0 - (pred_cost / max(1.0, budget.max_cost_tokens)), 0.0, 1.0)

    return {
        "similarity": similarity,
        "competence": competence,
        "reliability": reliability,
        "success_rate": success_rate,
        "oracle_history": oracle_history,
        "latency_efficiency": latency_efficiency,
        "cost_efficiency": cost_efficiency,
        "memory_alignment": _clamp(float(memory_alignment), 0.0, 1.0),
    }


def _utility_from_expected_success(expected_success: float, features: Mapping[str, float], budget_mode: str) -> float:
    profile = BUDGET_PROFILES.get(str(budget_mode), BUDGET_PROFILES["balanced"])
    quality_weight = float(profile["quality_weight"])
    cost_weight = float(profile["cost_weight"])
    latency_weight = float(profile["latency_weight"])

    cost_efficiency = _clamp(float(features.get("cost_efficiency", 0.0)), 0.0, 1.0)
    latency_efficiency = _clamp(float(features.get("latency_efficiency", 0.0)), 0.0, 1.0)

    utility = (
        (quality_weight * _clamp(float(expected_success), 0.0, 1.0))
        + (cost_weight * cost_efficiency)
        + (latency_weight * latency_efficiency)
    )
    return _clamp(utility, 0.0, 1.0)


class RouterV3:
    """
    Learned Router v3.

    - Loads local lightweight model from models/router_v3.pt if available.
    - Falls back to deterministic default weights when model file is missing.
    - Uses contract embeddings + history/budget features.
    """

    def __init__(
        self,
        agents: Sequence[BaseAgent],
        *,
        seed: int = 0,
        model_path: str = "models/router_v3.pt",
        embedding_dim: int = 24,
        default_budget_mode: str = "balanced",
        base_exploration: float = 0.04,
        min_exploration: float = 0.01,
        max_exploration: float = 0.22,
    ) -> None:
        self.agents: List[BaseAgent] = list(agents)
        self.seed = int(seed)
        self.embedding_dim = int(embedding_dim)
        self.model_path = str(model_path)
        self.model = load_router_v3_model(self.model_path, seed=self.seed)
        self.default_budget_mode = str(default_budget_mode)

        self.base_exploration = float(base_exploration)
        self.min_exploration = float(min_exploration)
        self.max_exploration = float(max_exploration)

    def reload_model(self) -> None:
        self.model = load_router_v3_model(self.model_path, seed=self.seed)

    def _call_rng(self, prompt: str, task_metadata: Mapping[str, Any] | None) -> random.Random:
        task_id = ""
        if task_metadata:
            task_id = str(task_metadata.get("task_id") or "")
        raw = f"{self.seed}|{task_id}|{prompt}".encode("utf-8")
        digest = hashlib.sha256(raw).hexdigest()
        return random.Random(int(digest[:16], 16))

    def _budget_obj(self, budget: RoutingBudget | Mapping[str, Any] | None) -> RoutingBudget:
        if budget is None:
            return RoutingBudget()
        if isinstance(budget, RoutingBudget):
            return budget
        return RoutingBudget(
            max_latency_ms=float(budget.get("max_latency_ms", 1500.0)),
            max_cost_tokens=float(budget.get("max_cost_tokens", 512.0)),
            latency_weight=float(budget.get("latency_weight", 0.5)),
            cost_weight=float(budget.get("cost_weight", 0.5)),
        )

    def _budget_mode(self, budget: RoutingBudget | Mapping[str, Any] | None) -> str:
        if isinstance(budget, Mapping):
            mode = str(budget.get("mode", "") or "").strip().lower()
            if mode in BUDGET_PROFILES:
                return mode
        return self.default_budget_mode if self.default_budget_mode in BUDGET_PROFILES else "balanced"

    def _history_row(self, history_stats: Mapping[str, Any] | None, agent_name: str, fallback: Contract) -> Dict[str, float]:
        if history_stats and isinstance(history_stats.get(agent_name), Mapping):
            row = history_stats.get(agent_name) or {}
            return {
                "success_rate": _clamp(float(row.get("success_rate", fallback.reliability)), 0.0, 1.0),
                "avg_oracle_score": _clamp(float(row.get("avg_oracle_score", fallback.reliability)), 0.0, 1.0),
                "avg_latency_ms": max(1.0, float(row.get("avg_latency_ms", 120.0 + (860.0 * fallback.cost_prior)))),
                "avg_cost_tokens": max(1.0, float(row.get("avg_cost_tokens", 64.0 + (460.0 * fallback.cost_prior)))),
            }

        return {
            "success_rate": _clamp(float(fallback.reliability), 0.0, 1.0),
            "avg_oracle_score": _clamp(float(fallback.reliability), 0.0, 1.0),
            "avg_latency_ms": 120.0 + (860.0 * float(fallback.cost_prior)),
            "avg_cost_tokens": 64.0 + (460.0 * float(fallback.cost_prior)),
        }

    def _memory_alignment(self, memory_hints: Mapping[str, Any] | None, agent_name: str) -> float:
        if not memory_hints:
            return 0.5
        if agent_name in memory_hints:
            return _clamp(float(memory_hints.get(agent_name, 0.5)), 0.0, 1.0)
        if "default" in memory_hints:
            return _clamp(float(memory_hints.get("default", 0.5)), 0.0, 1.0)
        return 0.5

    def _exploration_probability(self, ranked_decisions: Sequence[RouteDecisionV3]) -> float:
        if not ranked_decisions:
            return self.min_exploration

        top = float(ranked_decisions[0].expected_utility)
        second = float(ranked_decisions[1].expected_utility) if len(ranked_decisions) > 1 else top
        margin = _clamp(top - second, 0.0, 1.0)
        eps = self.base_exploration + (0.25 * (1.0 - margin))
        return _clamp(eps, self.min_exploration, self.max_exploration)

    def route_top_k(
        self,
        prompt: str,
        k: int = 2,
        *,
        task_metadata: Optional[Mapping[str, Any]] = None,
        memory_hints: Optional[Mapping[str, Any]] = None,
        budget: Optional[RoutingBudget | Mapping[str, Any]] = None,
        history_stats: Optional[Mapping[str, Any]] = None,
        budget_mode: Optional[str] = None,
    ) -> Tuple[List[BaseAgent], List[RouteDecisionV3]]:
        if not self.agents:
            return [], []

        k = max(1, min(int(k), len(self.agents)))
        budget_obj = self._budget_obj(budget)
        chosen_budget_mode = str(budget_mode or self._budget_mode(budget)).strip().lower()
        if chosen_budget_mode not in BUDGET_PROFILES:
            chosen_budget_mode = "balanced"

        scored: List[Tuple[float, str, BaseAgent, Dict[str, float], float]] = []
        for agent in self.agents:
            contract = agent.contract
            agent_name = str(contract.name)

            history_row = self._history_row(history_stats, agent_name, contract)
            memory_alignment = self._memory_alignment(memory_hints, agent_name)
            features = build_router_v3_features(
                prompt,
                contract,
                history_row=history_row,
                memory_alignment=memory_alignment,
                budget=budget_obj,
                embedding_dim=self.embedding_dim,
                seed=self.seed,
            )
            expected_success = _clamp(self.model.predict_expected_success(features), 0.0, 1.0)
            utility = _utility_from_expected_success(expected_success, features, chosen_budget_mode)

            scored.append((float(utility), agent_name, agent, features, expected_success))

        scored.sort(key=lambda row: (row[0], row[1]), reverse=True)

        decisions: List[RouteDecisionV3] = []
        for utility, agent_name, _agent, features, expected_success in scored:
            profile = BUDGET_PROFILES[chosen_budget_mode]
            rationale = (
                f"expected_success={expected_success:.3f}; "
                f"sim={features['similarity']:.2f}; "
                f"budget={chosen_budget_mode}; "
                f"w=({profile['quality_weight']:.2f},{profile['cost_weight']:.2f},{profile['latency_weight']:.2f})"
            )
            components = {k: float(v) for k, v in features.items()}
            components["expected_success"] = float(expected_success)
            components["budget_mode_value"] = {
                "cheap": 0.0,
                "balanced": 0.5,
                "max_quality": 1.0,
            }.get(chosen_budget_mode, 0.5)

            decisions.append(
                RouteDecisionV3(
                    agent_name=agent_name,
                    score=float(utility),
                    reason="router_v3_learned",
                    rationale=rationale,
                    exploration_probability=0.0,
                    expected_utility=float(utility),
                    selected_by_exploration=False,
                    components=components,
                )
            )

        eps = self._exploration_probability(decisions)
        ranked_agents = [row[2] for row in scored[:k]]
        ranked_decisions = [replace(d, exploration_probability=float(eps)) for d in decisions[:k]]
        return ranked_agents, ranked_decisions

    def route(
        self,
        prompt: str,
        *,
        task_metadata: Optional[Mapping[str, Any]] = None,
        memory_hints: Optional[Mapping[str, Any]] = None,
        budget: Optional[RoutingBudget | Mapping[str, Any]] = None,
        history_stats: Optional[Mapping[str, Any]] = None,
        top_k: int = 2,
        budget_mode: Optional[str] = None,
    ) -> Tuple[BaseAgent, RouteDecisionV3]:
        k = min(max(1, int(top_k)), len(self.agents))
        ranked_agents, ranked_decisions = self.route_top_k(
            prompt,
            k=max(2, k) if len(self.agents) > 1 else 1,
            task_metadata=task_metadata,
            memory_hints=memory_hints,
            budget=budget,
            history_stats=history_stats,
            budget_mode=budget_mode,
        )

        if not ranked_agents:
            raise ValueError("RouterV3 requires at least one agent")

        eps = float(ranked_decisions[0].exploration_probability)
        rng = self._call_rng(prompt, task_metadata)

        selected_idx = 0
        selected_by_exploration = False
        if len(ranked_agents) > 1 and rng.random() < eps:
            selected_idx = 1 + rng.randrange(len(ranked_agents) - 1)
            selected_by_exploration = True

        return ranked_agents[selected_idx], replace(
            ranked_decisions[selected_idx],
            selected_by_exploration=selected_by_exploration,
        )
