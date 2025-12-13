from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ArchitectOutput:
    plan: str
    confidence: float
    meta: dict


class ArchitectBrain:
    """
    Architect Brain:
    - Proposes structured plans
    - Optimistic by default
    - Does NOT verify truth
    """

    def propose(self, prompt: str) -> ArchitectOutput:
        # Phase 10 v1: simple structured plan
        plan = f"Proposed plan for: {prompt}"
        return ArchitectOutput(
            plan=plan,
            confidence=0.7,
            meta={"style": "architect-v1"},
        )
