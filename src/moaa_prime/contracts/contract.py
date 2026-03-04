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

    Later phases:
    - GCEL will mutate these fields.
    - Oracle/SFC will update trust scores.

    Cycle 2 additions:
    - reliability: prior trust in execution quality
    - cost_prior: prior expected cost/latency pressure (0 cheap .. 1 expensive)
    """

    name: str
    domains: List[str] = field(default_factory=list)
    tools: List[str] = field(default_factory=list)
    modalities: Dict[str, float] = field(default_factory=dict)  # e.g. {"vision": 0.2}
    competence: float = 0.75  # 0..1 (starter prior)
    reliability: float = 0.70  # 0..1
    cost_prior: float = 0.30  # 0..1
