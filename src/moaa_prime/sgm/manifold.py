from __future__ import annotations

from dataclasses import dataclass
from typing import List

from moaa_prime.memory.emre import _hash_embed


@dataclass
class SGMState:
    """Shared Geometric Manifold state (Phase 7 v0)."""
    vec: List[float]


class SharedGeometricManifold:
    """
    Phase 7 v0:
    - Deterministic embedding for text using our cheap hash-embed
    - Provides a shared "space" for fusion + later routing signals
    """

    def __init__(self, dim: int = 64) -> None:
        self.dim = int(dim)

    def embed(self, text: str) -> SGMState:
        v = _hash_embed(text, dim=self.dim)
        return SGMState(vec=v)
