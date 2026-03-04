from __future__ import annotations

import statistics
from typing import Any, Dict, List, Mapping, Optional, Union

from moaa_prime.router.meta_router import MetaRouter
from moaa_prime.swarm.pareto import pareto_frontier

try:
    from moaa_prime.oracle.verifier import OracleVerifier
except Exception:  # pragma: no cover
    OracleVerifier = None  # type: ignore

# Phase 7/8 optional imports
try:
    from moaa_prime.sgm import SharedGeometricManifold
    from moaa_prime.fusion import EnergyFusion
except Exception:  # pragma: no cover
    SharedGeometricManifold = None  # type: ignore
    EnergyFusion = None  # type: ignore


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


class SwarmManager:
    """
    SwarmManager (Phase 4–9 compatible + Cycle 2/3 mode support)

    GUARANTEES:
    - `run(...)` exists and returns {"best": ..., "candidates": [...]}.
    - v1/v2 legacy behavior preserved.
    - v3 adds Pareto-based selection with adaptive budget weighting.
    """

    def __init__(
        self,
        router_or_agents: Union[MetaRouter, List[Any]],
        oracle: Optional[OracleVerifier] = None,
        fusion_mode: Optional[str] = None,
        *,
        mode: str = "v1",
        seed: int = 0,
    ) -> None:
        self.router: Optional[MetaRouter] = None
        self._agents_override: Optional[List[Any]] = None

        if isinstance(router_or_agents, list):
            self._agents_override = router_or_agents
        else:
            self.router = router_or_agents

        self.oracle = oracle
        self.fusion_mode = fusion_mode
        self.mode = (mode or "v1").strip().lower()
        self.seed = int(seed)

        # Optional Phase 7/8 wiring (non-breaking)
        self.sgm = SharedGeometricManifold() if SharedGeometricManifold else None
        self.energy_fusion = EnergyFusion(self.sgm) if (EnergyFusion and self.sgm) else None

    # -----------------------------
    # Oracle helper
    # -----------------------------
    def _oracle_block(self, prompt: str, text: str) -> Dict[str, Any]:
        if self.oracle is None:
            return {"score": 0.5, "reason": "no oracle", "meta": {}}

        if hasattr(self.oracle, "verdict"):
            v = self.oracle.verdict(prompt, text)  # type: ignore[attr-defined]
            return {
                "score": float(getattr(v, "score", 0.5)),
                "reason": getattr(v, "reason", ""),
                "meta": getattr(v, "meta", {}) or {},
            }

        return {"score": float(self.oracle.score(prompt, text)), "reason": "", "meta": {}}

    def _build_router_trace(self, decisions: List[Any], chosen_mode: str) -> Dict[str, Any]:
        ranked: List[Dict[str, Any]] = []
        for d in decisions:
            comps = getattr(d, "components", {}) or {}
            ranked.append(
                {
                    "agent": getattr(d, "agent_name", ""),
                    "score": float(getattr(d, "score", 0.0)),
                    "expected_utility": float(getattr(d, "expected_utility", getattr(d, "score", 0.0))),
                    "exploration_probability": float(getattr(d, "exploration_probability", 0.0)),
                    "selected_by_exploration": bool(getattr(d, "selected_by_exploration", False)),
                    "reason": getattr(d, "reason", ""),
                    "rationale": getattr(d, "rationale", ""),
                    "components": comps,
                }
            )

        exploration_probability = 0.0
        if ranked:
            exploration_probability = float(ranked[0].get("exploration_probability", 0.0))

        return {
            "mode": chosen_mode,
            "ranked": ranked,
            "exploration_probability": exploration_probability,
        }

    # -----------------------------
    # Internal: get candidate agents
    # -----------------------------
    def _get_agents_and_decisions(
        self,
        prompt: str,
        top_k: int,
        *,
        task_metadata: Optional[Mapping[str, Any]] = None,
        memory_hints: Optional[Mapping[str, Any]] = None,
        budget: Optional[Mapping[str, Any]] = None,
        history_stats: Optional[Mapping[str, Any]] = None,
        budget_mode: Optional[str] = None,
    ) -> tuple[List[Any], List[Any]]:
        if self.router is not None:
            # RouterV3/RouterV2 supports richer kwargs; MetaRouter only accepts prompt/k.
            try:
                agents, decisions = self.router.route_top_k(  # type: ignore[misc]
                    prompt,
                    k=top_k,
                    task_metadata=task_metadata,
                    memory_hints=memory_hints,
                    budget=budget,
                    history_stats=history_stats,
                    budget_mode=budget_mode,
                )
                return list(agents), list(decisions)
            except TypeError:
                try:
                    agents, decisions = self.router.route_top_k(  # type: ignore[misc]
                        prompt,
                        k=top_k,
                        task_metadata=task_metadata,
                        memory_hints=memory_hints,
                        budget=budget,
                        history_stats=history_stats,
                    )
                    return list(agents), list(decisions)
                except TypeError:
                    agents, decisions = self.router.route_top_k(prompt, k=top_k)
                    return list(agents), list(decisions)

        if self._agents_override is not None:
            agents = list(self._agents_override)
            decisions: List[Dict[str, Any]] = []
            for idx, a in enumerate(agents[:top_k]):
                name = getattr(getattr(a, "contract", None), "name", getattr(a, "name", f"agent-{idx}"))
                decisions.append(
                    {
                        "agent_name": str(name),
                        "score": float(1.0 - (idx * 0.01)),
                        "reason": "agents_override",
                    }
                )
            return agents[:top_k], decisions

        return [], []

    def _candidate_prompt(self, prompt: str, agent: Any, round_idx: int, mode: str) -> str:
        if mode == "v1":
            return prompt

        contract = getattr(agent, "contract", None)
        domains = getattr(contract, "domains", []) if contract is not None else []
        domain_hint = ",".join(str(d) for d in domains) if domains else "general"

        if mode == "v3":
            return f"{prompt}\n[agent_domain={domain_hint}; round={round_idx + 1}; style=deliberative]"

        return f"{prompt}\n[agent_domain={domain_hint}; round={round_idx + 1}]"

    def _build_candidate(
        self,
        *,
        agent: Any,
        prompt: str,
        task_id: str,
        round_idx: int,
        rank_idx: int,
        mode: str,
    ) -> Dict[str, Any]:
        call_prompt = self._candidate_prompt(prompt, agent, round_idx, mode)

        try:
            result = agent.handle(call_prompt, task_id=task_id)
        except TypeError:
            result = agent.handle(call_prompt)

        text = getattr(result, "text", str(result))
        agent_name = getattr(result, "agent_name", getattr(agent, "name", "agent"))
        meta = getattr(result, "meta", {}) or {}

        oracle_block = self._oracle_block(prompt, text)

        token_count = max(1, len(str(text).split()))
        contract = getattr(agent, "contract", None)
        cost_prior = float(getattr(contract, "cost_prior", 0.3) or 0.3)

        latency_proxy = float(40 + (4 * token_count) + (8 * rank_idx) + (3 * round_idx) + int(20 * cost_prior))
        cost_proxy = float(16 + token_count + int(42 * cost_prior))

        grounding = float((((oracle_block.get("meta", {}) or {}).get("components", {}) or {}).get("grounding", oracle_block["score"])))
        confidence_proxy = _clamp((0.65 * float(oracle_block["score"])) + (0.35 * grounding), 0.0, 1.0)

        return {
            "agent": str(agent_name),
            "text": str(text),
            "meta": meta,
            "oracle": oracle_block,
            "round": int(round_idx + 1),
            "rank": int(rank_idx),
            "latency_proxy": latency_proxy,
            "cost_proxy": cost_proxy,
            "confidence_proxy": confidence_proxy,
        }

    def _apply_cross_critique(self, candidates: List[Dict[str, Any]], *, enabled: bool) -> Dict[str, Any]:
        if not enabled:
            return {"enabled": False, "status": "disabled"}
        if len(candidates) < 2:
            return {"enabled": True, "status": "insufficient-candidates"}

        ranked = sorted(candidates, key=lambda c: float((c.get("oracle", {}) or {}).get("score", 0.0)), reverse=True)
        c1 = ranked[0]
        c2 = ranked[1]

        note_1 = f"Critique against {c2['agent']}: strengthen grounding and constraints."
        note_2 = f"Critique against {c1['agent']}: improve directness and correctness."

        c1["critique"] = note_1
        c2["critique"] = note_2

        c1["confidence_proxy"] = _clamp(float(c1.get("confidence_proxy", 0.5)) + 0.02, 0.0, 1.0)
        c2["confidence_proxy"] = _clamp(float(c2.get("confidence_proxy", 0.5)) + 0.01, 0.0, 1.0)

        return {
            "enabled": True,
            "status": "top2-critique-applied",
            "candidate_a": c1["agent"],
            "candidate_b": c2["agent"],
        }

    def _select_best_legacy(self, candidates: List[Dict[str, Any]], *, cross_check: bool = False) -> tuple[Dict[str, Any], float, Dict[str, Any]]:
        if not candidates:
            return (
                {
                    "agent": "",
                    "text": "",
                    "meta": {},
                    "oracle": {"score": 0.0, "reason": "no candidates", "meta": {}},
                    "round": 0,
                    "rank": 0,
                    "latency_proxy": 0.0,
                    "cost_proxy": 0.0,
                    "confidence_proxy": 0.0,
                },
                0.0,
                {"enabled": cross_check, "status": "no-candidates"},
            )

        ranked = sorted(candidates, key=lambda c: float((c.get("oracle", {}) or {}).get("score", 0.0)), reverse=True)
        best = ranked[0]

        second_score = float((ranked[1].get("oracle", {}) or {}).get("score", 0.0)) if len(ranked) > 1 else float((best.get("oracle", {}) or {}).get("score", 0.0))
        margin = _clamp(float((best.get("oracle", {}) or {}).get("score", 0.0)) - second_score, 0.0, 1.0)

        values = [float((c.get("oracle", {}) or {}).get("score", 0.0)) for c in ranked]
        dispersion = float(statistics.pstdev(values)) if len(values) > 1 else 0.0
        confidence = _clamp(0.55 + (0.35 * margin) + (0.10 * (1.0 - dispersion)), 0.0, 1.0)

        cross_meta: Dict[str, Any] = {"enabled": bool(cross_check), "status": "disabled"}
        if cross_check and len(ranked) > 1:
            c1 = ranked[0]
            c2 = ranked[1]
            c1_components = ((c1.get("oracle", {}) or {}).get("meta", {}) or {}).get("components", {}) or {}
            c2_components = ((c2.get("oracle", {}) or {}).get("meta", {}) or {}).get("components", {}) or {}
            c1_ground = float(c1_components.get("grounding", 0.0))
            c2_ground = float(c2_components.get("grounding", 0.0))
            winner = c1 if c1_ground >= c2_ground else c2
            best = winner
            confidence = _clamp(confidence + 0.03, 0.0, 1.0)
            cross_meta = {
                "enabled": True,
                "status": "top2_stubbed",
                "candidate_a": c1["agent"],
                "candidate_b": c2["agent"],
                "winner": best["agent"],
                "grounding_a": c1_ground,
                "grounding_b": c2_ground,
            }

        return best, confidence, cross_meta

    def _select_best_v3(self, candidates: List[Dict[str, Any]], *, budget_mode: str) -> tuple[Dict[str, Any], float, Dict[str, Any]]:
        if not candidates:
            return (
                {
                    "agent": "",
                    "text": "",
                    "meta": {},
                    "oracle": {"score": 0.0, "reason": "no candidates", "meta": {}},
                    "round": 0,
                    "rank": 0,
                    "latency_proxy": 0.0,
                    "cost_proxy": 0.0,
                    "confidence_proxy": 0.0,
                },
                0.0,
                {"enabled": True, "status": "no-candidates", "frontier": []},
            )

        profile_map = {
            "cheap": {"score": 0.45, "confidence": 0.10, "latency": 0.20, "cost": 0.25},
            "balanced": {"score": 0.60, "confidence": 0.15, "latency": 0.13, "cost": 0.12},
            "max_quality": {"score": 0.78, "confidence": 0.18, "latency": 0.02, "cost": 0.02},
        }
        profile = profile_map.get(budget_mode, profile_map["balanced"])

        max_latency = max(float(c.get("latency_proxy", 0.0)) for c in candidates)
        max_cost = max(float(c.get("cost_proxy", 0.0)) for c in candidates)
        max_latency = max(1.0, max_latency)
        max_cost = max(1.0, max_cost)

        points = []
        for idx, c in enumerate(candidates):
            points.append(
                {
                    "id": float(idx),
                    "score": float((c.get("oracle", {}) or {}).get("score", 0.0)),
                    "confidence": float(c.get("confidence_proxy", 0.5)),
                    "latency": float(c.get("latency_proxy", 0.0)),
                    "cost": float(c.get("cost_proxy", 0.0)),
                }
            )

        frontier = pareto_frontier(points)
        frontier_ids = [int(p.get("id", 0.0)) for p in frontier]
        frontier_candidates = [candidates[i] for i in frontier_ids if 0 <= i < len(candidates)]
        if not frontier_candidates:
            frontier_candidates = list(candidates)

        def _utility(c: Dict[str, Any]) -> float:
            score = float((c.get("oracle", {}) or {}).get("score", 0.0))
            conf = float(c.get("confidence_proxy", 0.5))
            lat_eff = _clamp(1.0 - (float(c.get("latency_proxy", 0.0)) / max_latency), 0.0, 1.0)
            cost_eff = _clamp(1.0 - (float(c.get("cost_proxy", 0.0)) / max_cost), 0.0, 1.0)
            return _clamp(
                (profile["score"] * score)
                + (profile["confidence"] * conf)
                + (profile["latency"] * lat_eff)
                + (profile["cost"] * cost_eff),
                0.0,
                1.0,
            )

        best = max(
            frontier_candidates,
            key=lambda c: (
                _utility(c),
                float((c.get("oracle", {}) or {}).get("score", 0.0)),
                -float(c.get("latency_proxy", 0.0)),
                -float(c.get("cost_proxy", 0.0)),
            ),
        )
        confidence = _clamp(float(best.get("confidence_proxy", 0.5)), 0.0, 1.0)

        frontier_meta = [
            {
                "agent": c.get("agent", ""),
                "score": float((c.get("oracle", {}) or {}).get("score", 0.0)),
                "confidence": float(c.get("confidence_proxy", 0.0)),
                "latency": float(c.get("latency_proxy", 0.0)),
                "cost": float(c.get("cost_proxy", 0.0)),
            }
            for c in frontier_candidates
        ]

        return best, confidence, {
            "enabled": True,
            "status": "pareto-selected",
            "budget_mode": budget_mode,
            "profile": profile,
            "frontier": frontier_meta,
        }

    def _aggregate_proxies(self, candidates: List[Dict[str, Any]]) -> Dict[str, float]:
        if not candidates:
            return {"avg_latency_proxy": 0.0, "avg_cost_proxy": 0.0}

        avg_latency = sum(float(c.get("latency_proxy", 0.0)) for c in candidates) / float(len(candidates))
        avg_cost = sum(float(c.get("cost_proxy", 0.0)) for c in candidates) / float(len(candidates))
        return {
            "avg_latency_proxy": float(avg_latency),
            "avg_cost_proxy": float(avg_cost),
        }

    # -----------------------------
    # Phase 4 main API (must exist)
    # -----------------------------
    def run(
        self,
        prompt: str,
        task_id: str = "default",
        rounds: int = 2,
        top_k: int = 2,
        *,
        mode: Optional[str] = None,
        task_metadata: Optional[Mapping[str, Any]] = None,
        memory_hints: Optional[Mapping[str, Any]] = None,
        budget: Optional[Mapping[str, Any]] = None,
        history_stats: Optional[Mapping[str, Any]] = None,
        cross_check: bool = False,
    ) -> Dict[str, Any]:
        chosen_mode = (mode or self.mode or "v1").strip().lower()
        if chosen_mode not in {"v1", "v2", "v3"}:
            chosen_mode = "v1"

        budget_mode = "balanced"
        if isinstance(budget, Mapping):
            maybe_mode = str(budget.get("mode", "") or "").strip().lower()
            if maybe_mode in {"cheap", "balanced", "max_quality"}:
                budget_mode = maybe_mode

        agents, decisions = self._get_agents_and_decisions(
            prompt,
            top_k=top_k,
            task_metadata=task_metadata,
            memory_hints=memory_hints,
            budget=budget,
            history_stats=history_stats,
            budget_mode=budget_mode,
        )

        candidates: List[Dict[str, Any]] = []
        for round_idx in range(max(1, int(rounds))):
            for rank_idx, agent in enumerate(agents):
                candidates.append(
                    self._build_candidate(
                        agent=agent,
                        prompt=prompt,
                        task_id=task_id,
                        round_idx=round_idx,
                        rank_idx=rank_idx,
                        mode=chosen_mode,
                    )
                )

        cross_meta = {"enabled": False, "status": "disabled"}
        pareto_meta = {"enabled": False, "status": "not-used", "frontier": []}

        if chosen_mode == "v3":
            cross_meta = self._apply_cross_critique(candidates, enabled=bool(cross_check))
            best, confidence, pareto_meta = self._select_best_v3(candidates, budget_mode=budget_mode)
        else:
            best, confidence, cross_meta = self._select_best_legacy(
                candidates,
                cross_check=(chosen_mode == "v2" and bool(cross_check)),
            )

        aggregates = self._aggregate_proxies(candidates)

        trace = {
            "router": self._build_router_trace(decisions, chosen_mode),
            "swarm": {
                "mode": chosen_mode,
                "rounds": int(max(1, rounds)),
                "top_k": int(max(1, top_k)),
                "num_candidates": int(len(candidates)),
                "cross_check": cross_meta,
                "pareto": pareto_meta,
                "budget_mode": budget_mode,
            },
            "oracle": {
                "mode": "oracle_v2" if chosen_mode in {"v2", "v3"} else "oracle_v1",
                "scores": [
                    {
                        "agent": c["agent"],
                        "score": float((c.get("oracle", {}) or {}).get("score", 0.0)),
                        "reason": (c.get("oracle", {}) or {}).get("reason", ""),
                        "components": ((c.get("oracle", {}) or {}).get("meta", {}) or {}).get("components", {}),
                    }
                    for c in candidates
                ],
            },
            "final": {
                "agent": best.get("agent", ""),
                "score": float((best.get("oracle", {}) or {}).get("score", 0.0)),
                "confidence": float(confidence),
                "budget_mode": budget_mode,
            },
        }

        if not candidates:
            return {
                "best": best,
                "candidates": [],
                "confidence": float(confidence),
                "trace": trace,
                "mode": chosen_mode,
                **aggregates,
            }

        return {
            "best": best,
            "candidates": candidates,
            "confidence": float(confidence),
            "trace": trace,
            "mode": chosen_mode,
            **aggregates,
        }

    # -----------------------------
    # Phase 8 experimental API (optional)
    # -----------------------------
    def deliberate(self, prompt: str, rounds: int = 2) -> str:
        """
        Experimental: return only the chosen text.
        Does NOT replace Phase 4 contract; `run()` remains canonical.
        """
        out = self.run(prompt=prompt, task_id="default", rounds=rounds, top_k=2)
        candidates = [c["text"] for c in out.get("candidates", [])]

        if not candidates:
            return ""

        if self.fusion_mode == "energy" and self.energy_fusion and self.oracle:
            pick = self.energy_fusion.pick(prompt, candidates, oracle_score=self.oracle.score)
            return pick.text

        best = out.get("best", {})
        if isinstance(best, dict):
            return str(best.get("text", ""))

        if self.oracle:
            return max(candidates, key=lambda c: float(self.oracle.score(prompt, c)))

        return candidates[0]
