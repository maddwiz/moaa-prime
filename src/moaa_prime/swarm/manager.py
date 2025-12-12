from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from moaa_prime.oracle import OracleVerifier
from moaa_prime.router import MetaRouter


@dataclass
class SwarmPick:
    agent: str
    text: str
    oracle_score: float
    oracle_reason: str


class SwarmManager:
    """
    Phase 4: minimal swarm:
    - ask top-k agents for answers
    - score each answer with Oracle
    - return the best one + full trace
    """

    def __init__(self, router: MetaRouter, oracle: OracleVerifier, k: int = 2) -> None:
        self.router = router
        self.oracle = oracle
        self.k = k

    def run(self, prompt: str) -> Dict[str, Any]:
        candidates = self.router.top_k(prompt, k=self.k)

        picks: List[SwarmPick] = []
        for agent, decision in candidates:
            result = agent.handle(prompt)

            o = self.oracle.verify(
                prompt=prompt,
                answer=result.text,
                agent_name=result.agent_name,
            )

            picks.append(
                SwarmPick(
                    agent=result.agent_name,
                    text=result.text,
                    oracle_score=float(o.score),
                    oracle_reason=str(o.reason),
                )
            )

        best = max(picks, key=lambda p: p.oracle_score)

        return {
            "prompt": prompt,
            "candidates": [
                {
                    "agent": p.agent,
                    "text": p.text,
                    "oracle": {"score": p.oracle_score, "reason": p.oracle_reason},
                }
                for p in picks
            ],
            "best": {
                "agent": best.agent,
                "text": best.text,
                "oracle": {"score": best.oracle_score, "reason": best.oracle_reason},
            },
        }
