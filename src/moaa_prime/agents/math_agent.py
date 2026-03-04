from __future__ import annotations

from dataclasses import asdict

from moaa_prime.agents.base import AgentResult, BaseAgent
from moaa_prime.policy import run_math_tool_first


class MathAgent(BaseAgent):
    def handle(self, prompt: str, task_id: str = "default") -> AgentResult:
        outcome = run_math_tool_first(prompt)

        if not outcome.success:
            fallback = super().handle(prompt, task_id=task_id)
            meta = dict(fallback.meta or {})
            meta["tool_first"] = asdict(outcome)
            return AgentResult(agent_name=fallback.agent_name, text=fallback.text, meta=meta)

        recall_meta = self._bank_recall(task_id=task_id, prompt=prompt)
        write_meta = self._bank_write(task_id=task_id, prompt=prompt, text=outcome.text)

        return AgentResult(
            agent_name=self.contract.name,
            text=outcome.text,
            meta={
                "model": "tool_first:sympy",
                "memory": self._memory_meta(task_id=task_id, recall_meta=recall_meta, write_meta=write_meta),
                "tool_first": asdict(outcome),
            },
        )
