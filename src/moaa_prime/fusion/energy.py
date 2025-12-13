from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Tuple

from moaa_prime.sgm.manifold import SharedGeometricManifold


@dataclass(frozen=True)
class FusionPick:
    text: str
    energy: float
    reason: str


class EnergyFusion:
    """
    Phase 7 v0:
    Pick best candidate by minimizing a simple "energy":
      energy = -oracle_score + (small_penalty * length_norm)

    Later we can add:
      + diversity bonus, + manifold consistency, + SFC budget coupling, etc.
    """

    def __init__(self, sgm: SharedGeometricManifold, length_penalty: float = 0.002) -> None:
        self.sgm = sgm
        self.length_penalty = float(length_penalty)

    def pick(
        self,
        prompt: str,
        candidates: List[str],
        oracle_score: Callable[[str, str], float],
    ) -> FusionPick:
        if not candidates:
            return FusionPick(text="", energy=1e9, reason="no candidates")

        scored: List[Tuple[float, str, float]] = []
        for c in candidates:
            score = float(oracle_score(prompt, c))
            # tiny length penalty to avoid rambling
            energy = (-score) + self.length_penalty * (len(c) / 1000.0)
            scored.append((energy, c, score))

        scored.sort(key=lambda t: t[0])
        best_energy, best_text, best_score = scored[0]
        return FusionPick(
            text=best_text,
            energy=float(best_energy),
            reason=f"min_energy; oracle={best_score:.3f}",
        )
