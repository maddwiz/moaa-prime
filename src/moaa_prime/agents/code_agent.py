from __future__ import annotations

from dataclasses import asdict
from typing import Optional

from moaa_prime.agents.base import AgentResult, BaseAgent
from moaa_prime.llm import LLMClient
from moaa_prime.policy import run_code_tool_first


class CodeAgent(BaseAgent):
    def __init__(
        self,
        contract,
        *,
        bank=None,
        llm: Optional[LLMClient] = None,
        system_prompt: str = "",
        max_tool_retries: int = 2,
    ) -> None:
        super().__init__(contract, bank=bank, llm=llm, system_prompt=system_prompt)
        self.max_tool_retries = max(0, int(max_tool_retries))

    def _result_from_tool_outcome(
        self,
        *,
        prompt: str,
        task_id: str,
        outcome,
        model_name: str,
        extra_tool_meta: Optional[dict] = None,
    ) -> AgentResult:
        recall_meta = self._bank_recall(task_id=task_id, prompt=prompt)
        write_meta = self._bank_write(task_id=task_id, prompt=prompt, text=outcome.text)
        tool_meta = asdict(outcome)
        if extra_tool_meta:
            tool_meta.update(extra_tool_meta)

        return AgentResult(
            agent_name=self.contract.name,
            text=outcome.text,
            meta={
                "model": model_name,
                "memory": self._memory_meta(task_id=task_id, recall_meta=recall_meta, write_meta=write_meta),
                "tool_first": tool_meta,
            },
        )

    def handle(self, prompt: str, task_id: str = "default") -> AgentResult:
        prompt_outcome = run_code_tool_first(prompt, max_retries=self.max_tool_retries, execute=True)

        # If prompt already includes code, verify/repair deterministically directly.
        if prompt_outcome.attempted:
            return self._result_from_tool_outcome(
                prompt=prompt,
                task_id=task_id,
                outcome=prompt_outcome,
                model_name="tool_first:python_verify",
                extra_tool_meta={"source": "prompt"},
            )

        # PR-1 policy: propose code first, then verify + deterministic repair loop.
        proposal = self.llm.generate(prompt, system=self.system_prompt)
        proposal_outcome = run_code_tool_first(proposal.text, max_retries=self.max_tool_retries, execute=True)
        if proposal_outcome.attempted:
            return self._result_from_tool_outcome(
                prompt=prompt,
                task_id=task_id,
                outcome=proposal_outcome,
                model_name=proposal.model,
                extra_tool_meta={
                    "source": "llm_proposal",
                    "proposal_model": proposal.model,
                    "proposal_text": proposal.text,
                    "prompt_probe": asdict(prompt_outcome),
                },
            )

        # If proposal is non-code, preserve legacy fallback behavior using the proposal text.
        recall_meta = self._bank_recall(task_id=task_id, prompt=prompt)
        write_meta = self._bank_write(task_id=task_id, prompt=prompt, text=proposal.text)
        return AgentResult(
            agent_name=self.contract.name,
            text=proposal.text,
            meta={
                "model": proposal.model,
                "memory": self._memory_meta(task_id=task_id, recall_meta=recall_meta, write_meta=write_meta),
                "tool_first": {
                    "source": "llm_fallback",
                    "prompt_probe": asdict(prompt_outcome),
                    "proposal_probe": asdict(proposal_outcome),
                    "proposal_model": proposal.model,
                },
            },
        )
