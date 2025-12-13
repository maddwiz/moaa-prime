from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

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


class SwarmManager:
    """
    SwarmManager (Phase 4–9 compatible)

    GUARANTEES:
    - `run(...)` exists and returns {"best": ..., "candidates": [...]}
    - If constructed with MetaRouter: Phase 4 behavior (route_top_k, oracle blocks)
    - If constructed with a raw agent list: still supports `run(...)` using that list
      (needed for Phase 8/9 experimentation + tests)
    """

    def __init__(
        self,
        router_or_agents: Union[MetaRouter, List[Any]],
        oracle: Optional[OracleVerifier] = None,
        fusion_mode: Optional[str] = None,
    ) -> None:
        self.router: Optional[MetaRouter] = None
        self._agents_override: Optional[List[Any]] = None

        if isinstance(router_or_agents, list):
            self._agents_override = router_or_agents
        else:
            self.router = router_or_agents

        self.oracle = oracle
        self.fusion_mode = fusion_mode

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

    # -----------------------------
    # Internal: get candidate agents
    # -----------------------------
    def _get_agents(self, prompt: str, top_k: int) -> List[Any]:
        if self.router is not None:
            agents, _decision = self.router.route_top_k(prompt, k=top_k)
            return list(agents)

        if self._agents_override is not None:
            return list(self._agents_override)

        return []

    # -----------------------------
    # Phase 4 main API (must exist)
    # -----------------------------
    def run(
        self,
        prompt: str,
        task_id: str = "default",
        rounds: int = 2,
        top_k: int = 2,
    ) -> Dict[str, Any]:
        agents = self._get_agents(prompt, top_k=top_k)

        candidates: List[Dict[str, Any]] = []
        for _ in range(rounds):
            for agent in agents:
                # Some agents accept task_id, some don't. Try both.
                try:
                    result = agent.handle(prompt, task_id=task_id)
                except TypeError:
                    result = agent.handle(prompt)

                text = getattr(result, "text", str(result))
                agent_name = getattr(result, "agent_name", getattr(agent, "name", "agent"))
                meta = getattr(result, "meta", {}) or {}

                oracle_block = self._oracle_block(prompt, text)
                candidates.append(
                    {
                        "agent": agent_name,
                        "text": text,
                        "meta": meta,
                        "oracle": oracle_block,
                    }
                )

        if not candidates:
            return {"best": {"agent": "", "text": "", "meta": {}, "oracle": {"score": 0.0, "reason": "no candidates", "meta": {}}}, "candidates": []}

        # Default: "best" = max oracle score (Phase 4 contract)
        best = max(candidates, key=lambda c: float(c["oracle"]["score"]))
        return {"best": best, "candidates": candidates}

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

        # Default: oracle max
        if self.oracle:
            return max(candidates, key=lambda c: float(self.oracle.score(prompt, c)))

        return candidates[0]
