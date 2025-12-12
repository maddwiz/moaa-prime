from __future__ import annotations

from moaa_prime.agents.base import AgentResult, BaseAgent


class CodeAgent(BaseAgent):
    def handle(self, prompt: str) -> AgentResult:
        return AgentResult(
            agent_name=self.name,
            text=f"[code-agent stub] I received: {prompt}",
            meta={"routed": "code"},
        )
