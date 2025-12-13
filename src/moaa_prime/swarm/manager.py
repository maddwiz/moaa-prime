from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, List, Optional, Tuple

from moaa_prime.router.meta_router import MetaRouter

try:
    from moaa_prime.oracle.verifier import OracleVerifier, OracleVerdict
except Exception:  # pragma: no cover
    OracleVerifier = None  # type: ignore
    OracleVerdict = None  # type: ignore


class SwarmManager:
    """
    Phase 4: Swarm debate manager.

    Contract:
    - run(...) returns:
      {
        "best": { ... includes "oracle": {"score": float, ...} ... },
        "candidates": [ ... each includes "oracle" ... ]
      }
    """

    def __init__(self, router: MetaRouter, oracle: Optional[OracleVerifier] = None) -> None:
        self.router = router
        self.oracle = oracle

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

    def run(
        self,
        prompt: str,
        task_id: str = "default",
        rounds: int = 2,
        top_k: int = 2,
    ) -> Dict[str, Any]:
        # pick top_k agents
        agents, _decision = self.router.route_top_k(prompt, k=top_k)

        candidates: List[Dict[str, Any]] = []
        for agent in agents:
            result = agent.handle(prompt, task_id=task_id)
            oracle_block = self._oracle_block(prompt, result.text)
            candidates.append(
                {
                    "agent": result.agent_name,
                    "text": result.text,
                    "meta": result.meta or {},
                    "oracle": oracle_block,
                }
            )

        # "best" = max oracle score
        best = max(candidates, key=lambda c: float(c["oracle"]["score"]))

        return {"best": best, "candidates": candidates}
