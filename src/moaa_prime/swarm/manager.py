from __future__ import annotations

import statistics
from typing import Any, Dict, List, Mapping, Optional, Union

from moaa_prime.router.meta_router import MetaRouter

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
    SwarmManager (Phase 4–9 compatible + Cycle 2 v2 mode)

    GUARANTEES:
    - `run(...)` exists and returns {"best": ..., "candidates": [...]}.
    - If constructed with MetaRouter: router-driven behavior.
    - If constructed with a raw agent list: still supports `run(...)`.
    - v2 mode emits structured trace under `trace`.
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

        # Prefer rich verdict if available
        if hasattr(self.oracle, "verdict"):
            v = self.oracle.verdict(prompt, text)  # type: ignore[attr-defined]
            return {
                "score": float(getattr(v, "score", 0.5)),
                "reason": getattr(v, "reason", ""),
                "meta": getattr(v, "meta", {}) or {},
            }

        # Fallback: score-only
        return {"score": float(self.oracle.score(prompt, text)), "reason": "", "meta": {}}

    def _build_router_trace(self, decisions: List[Any]) -> Dict[str, Any]:
        ranked: List[Dict[str, Any]] = []
        for d in decisions:
            ranked.append(
                {
                    "agent": getattr(d, "agent_name", ""),
                    "score": float(getattr(d, "score", 0.0)),
                    "expected_utility": float(getattr(d, "expected_utility", getattr(d, "score", 0.0))),
                    "exploration_probability": float(getattr(d, "exploration_probability", 0.0)),
                    "selected_by_exploration": bool(getattr(d, "selected_by_exploration", False)),
                    "reason": getattr(d, "reason", ""),
                    "rationale": getattr(d, "rationale", ""),
                    "components": getattr(d, "components", {}) or {},
                }
            )

        exploration_probability = 0.0
        if ranked:
            exploration_probability = float(ranked[0].get("exploration_probability", 0.0))

        return {
            "mode": self.mode,
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
    ) -> tuple[List[Any], List[Any]]:
        if self.router is not None:
            # RouterV2 supports richer kwargs; MetaRouter only accepts prompt/k.
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

    def _candidate_prompt_v2(self, prompt: str, agent: Any, round_idx: int) -> str:
        contract = getattr(agent, "contract", None)
        domains = getattr(contract, "domains", []) if contract is not None else []
        domain_hint = ",".join(str(d) for d in domains) if domains else "general"
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
        call_prompt = prompt if mode == "v1" else self._candidate_prompt_v2(prompt, agent, round_idx)

        # Some agents accept task_id, some don't. Try both.
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

        return {
            "agent": str(agent_name),
            "text": str(text),
            "meta": meta,
            "oracle": oracle_block,
            "round": int(round_idx + 1),
            "rank": int(rank_idx),
            "latency_proxy": latency_proxy,
            "cost_proxy": cost_proxy,
        }

    def _select_best(self, candidates: List[Dict[str, Any]], *, cross_check: bool = False) -> tuple[Dict[str, Any], float, Dict[str, Any]]:
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
                },
                0.0,
                {"enabled": cross_check, "status": "no-candidates"},
            )

        ranked = sorted(candidates, key=lambda c: float(c["oracle"]["score"]), reverse=True)
        best = ranked[0]

        second_score = float(ranked[1]["oracle"]["score"]) if len(ranked) > 1 else float(best["oracle"]["score"])
        margin = _clamp(float(best["oracle"]["score"]) - second_score, 0.0, 1.0)

        values = [float(c["oracle"]["score"]) for c in ranked]
        dispersion = float(statistics.pstdev(values)) if len(values) > 1 else 0.0

        confidence = _clamp(0.55 + (0.35 * margin) + (0.10 * (1.0 - dispersion)), 0.0, 1.0)

        cross_meta: Dict[str, Any] = {"enabled": bool(cross_check), "status": "disabled"}
        if cross_check and len(ranked) > 1:
            c1 = ranked[0]
            c2 = ranked[1]
            c1_ground = float((c1.get("oracle", {}).get("meta", {}) or {}).get("components", {}).get("grounding", 0.0))
            c2_ground = float((c2.get("oracle", {}).get("meta", {}) or {}).get("components", {}).get("grounding", 0.0))
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

        agents, decisions = self._get_agents_and_decisions(
            prompt,
            top_k=top_k,
            task_metadata=task_metadata,
            memory_hints=memory_hints,
            budget=budget,
            history_stats=history_stats,
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

        best, confidence, cross_meta = self._select_best(candidates, cross_check=(chosen_mode == "v2" and bool(cross_check)))

        aggregates = self._aggregate_proxies(candidates)

        trace = {
            "router": self._build_router_trace(decisions),
            "swarm": {
                "mode": chosen_mode,
                "rounds": int(max(1, rounds)),
                "top_k": int(max(1, top_k)),
                "num_candidates": int(len(candidates)),
                "cross_check": cross_meta,
            },
            "oracle": {
                "mode": "oracle_v2" if chosen_mode == "v2" else "oracle_v1",
                "scores": [
                    {
                        "agent": c["agent"],
                        "score": float(c["oracle"]["score"]),
                        "reason": c["oracle"].get("reason", ""),
                        "components": (c["oracle"].get("meta", {}) or {}).get("components", {}),
                    }
                    for c in candidates
                ],
            },
            "final": {
                "agent": best.get("agent", ""),
                "score": float((best.get("oracle", {}) or {}).get("score", 0.0)),
                "confidence": float(confidence),
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

        # Optional energy fusion path (if wired)
        if self.fusion_mode == "energy" and self.energy_fusion and self.oracle:
            pick = self.energy_fusion.pick(prompt, candidates, oracle_score=self.oracle.score)
            return pick.text

        # Default: best from run output
        best = out.get("best", {})
        if isinstance(best, dict):
            return str(best.get("text", ""))

        if self.oracle:
            return max(candidates, key=lambda c: float(self.oracle.score(prompt, c)))

        return candidates[0]
