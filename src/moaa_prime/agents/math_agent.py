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

        write_meta = self._bank_write(task_id=task_id, prompt=prompt, text=outcome.text)
        recall_meta = self._bank_recall(task_id=task_id, prompt=prompt)

        return AgentResult(
            agent_name=self.contract.name,
            text=outcome.text,
            meta={
                "model": "tool_first:sympy",
                "memory": {
                    "local_hits": recall_meta["local_hits"],
                    "local_snippets": recall_meta["local_snippets"],
                    "bank_hits": recall_meta["bank_hits"],
                    "bank_snippets": recall_meta["bank_snippets"],
                    "write": write_meta,
                    "method": recall_meta["method"],
                    "task_id": task_id,
                },
                "tool_first": asdict(outcome),
            },
        )
