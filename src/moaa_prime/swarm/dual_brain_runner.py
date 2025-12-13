from __future__ import annotations

from moaa_prime.brains.architect import ArchitectBrain
from moaa_prime.brains.oracle_brain import OracleBrain


class DualBrainRunner:
    """
    Phase 10:
    Architect proposes → Oracle judges → result returned
    """

    def __init__(self):
        self.architect = ArchitectBrain()
        self.oracle = OracleBrain()

    def run(self, prompt: str) -> dict:
        proposal = self.architect.propose(prompt)
        judgement = self.oracle.judge(prompt, proposal.plan)

        return {
            "architect": {
                "plan": proposal.plan,
                "confidence": proposal.confidence,
                "meta": proposal.meta,
            },
            "oracle": {
                "approved": judgement.approved,
                "score": judgement.score,
                "reason": judgement.reason,
                "meta": judgement.meta,
            },
        }
