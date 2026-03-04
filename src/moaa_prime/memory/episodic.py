"""
Back-compat shim.

We used to define EpisodicLane here. Now the canonical implementation lives in:
  moaa_prime.memory.episodic_lane

Do not re-define classes in this file.
"""
from __future__ import annotations

from moaa_prime.memory.episodic_lane import EpisodicLane
from moaa_prime.memory.types import MemoryItem as Episode

__all__ = ["Episode", "EpisodicLane"]
