from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

from moaa_prime.agents.base import BaseAgent


@dataclass(frozen=True)
class RouteDecision:
    agent_name: str
    score: float
    reason: str


class MetaRouter:
    """
    Phase 2: keyword/domain router.
    Phase 4: add top_k() so SwarmManager can ask for multiple candidates.
    """

    def __init__(self, agents: List[BaseAgent]) -> None:
        self.agents = agents

    def _score(self, prompt: str, agent: BaseAgent) -> Tuple[float, str]:
        p = prompt.lower()
        domains = [d.lower() for d in (agent.contract.domains or [])]

        # very dumb heuristics (intentional for Phase 2/4)
        math_hits = any(k in p for k in ["solve", "equation", "integral", "derivative", "math", "algebra", "x +", "x=", "2x"])
        code_hits = any(k in p for k in ["code", "python", "bug", "stack trace", "function", "class", "import", "pip", "pytest", "exception"])

        score = 0.0
        reason = "default"

        if "math" in domains and math_hits:
            score += 1.3
            reason = "math-keywords"
        if "code" in domains and code_hits:
            score += 1.2
            reason = "code-keywords"

        # competence is a small nudge
        score += float(agent.contract.competence) * 0.1
        return score, reason

    def top_k(self, prompt: str, k: int = 2) -> List[Tuple[BaseAgent, RouteDecision]]:
        scored: List[Tuple[float, BaseAgent, str]] = []
        for agent in self.agents:
            s, r = self._score(prompt, agent)
            scored.append((s, agent, r))

        scored.sort(key=lambda t: t[0], reverse=True)
        top = scored[: max(1, k)]

        out: List[Tuple[BaseAgent, RouteDecision]] = []
        for s, agent, reason in top:
            out.append((agent, RouteDecision(agent_name=agent.contract.name, score=float(s), reason=reason)))
        return out

    def route(self, prompt: str) -> Tuple[BaseAgent, RouteDecision]:
        return self.top_k(prompt, k=1)[0]
