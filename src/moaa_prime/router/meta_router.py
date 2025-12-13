from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence, Tuple

from moaa_prime.agents.base import AgentResult, BaseAgent


@dataclass(frozen=True)
class RouteDecision:
    agent_name: str
    score: float
    reason: str = ""


class MetaRouter:
    """
    Phase 2 router.

    Contract:
    - route(prompt) -> (agent, decision)
    - route_top_k(prompt, k) -> (agents, decisions) sorted best->worst
    """

    def __init__(self, agents: Sequence[BaseAgent]) -> None:
        self.agents: List[BaseAgent] = list(agents)

    def _score(self, agent: BaseAgent, prompt: str) -> float:
        # v0 deterministic scoring: competence + tiny domain keyword bump
        score = float(getattr(agent.contract, "competence", 0.5) or 0.5)

        p = (prompt or "").lower()
        domains = [d.lower() for d in (agent.contract.domains or [])]

        if "math" in domains and ("solve" in p or "equation" in p or "x" in p):
            score += 0.10
        if "code" in domains and ("python" in p or "code" in p or "traceback" in p or "error" in p):
            score += 0.10

        if score < 0.0:
            return 0.0
        if score > 1.0:
            return 1.0
        return score

    def route(self, prompt: str) -> Tuple[BaseAgent, RouteDecision]:
        agents, decisions = self.route_top_k(prompt, k=1)
        return agents[0], decisions[0]

    def route_top_k(self, prompt: str, k: int = 2) -> Tuple[List[BaseAgent], List[RouteDecision]]:
        if k <= 0:
            k = 1
        k = min(k, len(self.agents))

        scored: List[Tuple[float, BaseAgent]] = []
        for a in self.agents:
            scored.append((self._score(a, prompt), a))

        scored.sort(key=lambda t: t[0], reverse=True)
        top = scored[:k]

        agents: List[BaseAgent] = []
        decisions: List[RouteDecision] = []
        for s, a in top:
            agents.append(a)
            decisions.append(RouteDecision(agent_name=a.contract.name, score=float(s), reason="router_score"))

        return agents, decisions
