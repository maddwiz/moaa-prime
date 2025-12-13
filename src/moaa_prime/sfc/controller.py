from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SFCState:
    """
    Stability Field Controller state.
    Value range is [0.0, 1.0]
    """
    value: float = 1.0  # start fully stable


class StabilityFieldController:
    """
    Phase 9 v0:
    Tracks stability using oracle score, energy, and novelty (kl_like).
    """

    def __init__(
        self,
        decay: float = 0.05,
        reward: float = 0.02,
        min_value: float = 0.0,
        max_value: float = 1.0,
    ) -> None:
        self.state = SFCState()
        self.decay = decay
        self.reward = reward
        self.min = min_value
        self.max = max_value

    def update(
        self,
        oracle_score: float,
        energy: float,
        kl_like: float,
    ) -> float:
        """
        Update stability:
        - reward good oracle scores
        - penalize high energy (conflict)
        - penalize high novelty (chaos)
        """
        delta = 0.0

        if oracle_score >= 0.75:
            delta += self.reward
        else:
            delta -= self.decay

        if energy > 0.5:
            delta -= self.decay

        if kl_like > 0.7:
            delta -= self.decay

        self.state.value += delta
        self.state.value = max(self.min, min(self.max, self.state.value))
        return self.state.value

    def should_continue(self) -> bool:
        """
        If stability collapses, stop reasoning loops.
        """
        return self.state.value >= 0.3
