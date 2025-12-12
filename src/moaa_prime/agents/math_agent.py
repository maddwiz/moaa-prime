from __future__ import annotations

from moaa_prime.agents.base import AgentResult, BaseAgent


class MathAgent(BaseAgent):
    def handle(self, prompt: str) -> AgentResult:
        # Phase 2 stub: we just label routing worked.
        return AgentResult(
            agent_name=self.name,
            text=f"[math-agent stub] I received: {prompt}",
            meta={"routed": "math"},
        )
