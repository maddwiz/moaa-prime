from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass
class Rng:
    """
    Tiny RNG wrapper so tests can be deterministic.
    """
    seed: int = 0

    def make(self) -> random.Random:
        return random.Random(self.seed)
