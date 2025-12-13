from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class MemoryWrite:
    """A single event we want to remember."""
    agent_name: str
    lane: str
    text: str
    task_id: str = "default"
    score: float = 0.0  # optional importance/utility
    meta: Optional[dict[str, Any]] = None


@dataclass(frozen=True)
class MemoryHit:
    """A retrieved memory item."""
    lane: str
    text: str
    score: float
    source: str  # "local" or "bank"
    agent_name: str
    task_id: str
