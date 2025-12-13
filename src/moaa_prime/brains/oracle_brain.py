from __future__ import annotations

from dataclasses import dataclass


@dataclass
class OracleJudgement:
    approved: bool
    score: float
    reason: str
    meta: dict


class OracleBrain:
    """
    Oracle Brain:
    - Skeptical by default
    - Can veto plans
    - Truth & consistency focused
    """

    def judge(self, prompt: str, plan: str) -> OracleJudgement:
        # Phase 10 v1: simple heuristic
        if "danger" in plan.lower():
            return OracleJudgement(
                approved=False,
                score=0.2,
                reason="Detected risky content",
                meta={"oracle": "v1"},
            )

        return OracleJudgement(
            approved=True,
            score=0.8,
            reason="Plan acceptable",
            meta={"oracle": "v1"},
        )
