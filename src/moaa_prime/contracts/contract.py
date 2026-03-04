from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass(frozen=True)
class Contract:
    """
    Lightweight "identity + promise" for an agent.

    Phase 2 goal:
    - Keep it dead-simple (no RL, no heavy routing).
    - Router chooses agent based on contract fields + cheap heuristics.

    Cycle 2 additions:
    - reliability: prior trust in execution quality
    - cost_prior: prior expected cost/latency pressure (0 cheap .. 1 expensive)

    Cycle 3 additions:
    - tags / description for semantic contract text
    - embedding for fast deterministic similarity routing
    """

    name: str
    domains: List[str] = field(default_factory=list)
    tools: List[str] = field(default_factory=list)
    modalities: Dict[str, float] = field(default_factory=dict)
    competence: float = 0.75
    reliability: float = 0.70
    cost_prior: float = 0.30
    tags: List[str] = field(default_factory=list)
    description: str = ""
    embedding: List[float] = field(default_factory=list)
