from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from moaa_prime.llm import LLMClient, StubLLMClient


@dataclass
class AgentResult:
    agent_name: str
    text: str
    meta: dict | None = None


class BaseAgent:
    """
    BaseAgent:
    - Owns a contract
    - Optionally owns memory (ReasoningBank)
    - Uses an LLMClient to generate responses

    Tests expect result.meta["memory"] to include at least:
      - local_hits
      - bank_hits
    """

    def __init__(
        self,
        contract,
        *,
        bank=None,
        llm: Optional[LLMClient] = None,
        system_prompt: str = "",
    ) -> None:
        self.contract = contract
        self.bank = bank
        self.llm = llm or StubLLMClient()
        self.system_prompt = system_prompt

    # -----------------------------
    # Memory helpers (best-effort)
    # -----------------------------
    def _bank_write(self, *, task_id: str, prompt: str, text: str) -> dict[str, Any]:
        meta: dict[str, Any] = {
            "task_id": task_id,
            "wrote": False,
            "method": None,
        }

        if self.bank is None:
            return meta

        payload = {
            "task_id": task_id,
            "agent": self.contract.name,
            "prompt": prompt,
            "text": text,
        }

        # Try a few common APIs (we keep this flexible so we don't break your bank design).
        try:
            if hasattr(self.bank, "write"):
                self.bank.write(payload)  # type: ignore[attr-defined]
                meta["wrote"] = True
                meta["method"] = "write(payload)"
                return meta
        except Exception:
            pass

        try:
            if hasattr(self.bank, "append"):
                self.bank.append(**payload)  # type: ignore[attr-defined]
                meta["wrote"] = True
                meta["method"] = "append(**payload)"
                return meta
        except Exception:
            pass

        meta["method"] = "no-write-method"
        return meta

    def _bank_recall(self, *, task_id: str, prompt: str) -> dict[str, Any]:
        """
        Returns a memory block that ALWAYS includes:
          - local_hits
          - bank_hits
        """
        mem: dict[str, Any] = {
            "task_id": task_id,
            "method": "no-recall-method",
            "local_hits": 0,
            "bank_hits": 0,
            "local_snippets": [],
            "bank_snippets": [],
        }

        if self.bank is None:
            return mem

        # Try common recall/query/search APIs
        try:
            if hasattr(self.bank, "recall"):
                out = self.bank.recall(task_id=task_id, query=prompt, k=5)  # type: ignore[attr-defined]
                mem["method"] = "recall(task_id,query,k)"
                if isinstance(out, dict):
                    # allow bank to return its own shape, but keep required keys
                    bank_snips = out.get("snippets", out.get("items", out.get("results", [])))
                    mem["bank_snippets"] = bank_snips if isinstance(bank_snips, list) else [bank_snips]
                    mem["bank_hits"] = len(mem["bank_snippets"])
                    # if bank reports local lane hits, accept it
                    if "local_hits" in out:
                        mem["local_hits"] = int(out["local_hits"])
                    return mem

                if isinstance(out, list):
                    mem["bank_snippets"] = out
                    mem["bank_hits"] = len(out)
                    return mem
        except Exception:
            pass

        try:
            if hasattr(self.bank, "search"):
                out = self.bank.search(task_id=task_id, query=prompt, k=5)  # type: ignore[attr-defined]
                mem["method"] = "search(task_id,query,k)"
                if isinstance(out, list):
                    mem["bank_snippets"] = out
                    mem["bank_hits"] = len(out)
                return mem
        except Exception:
            pass

        try:
            if hasattr(self.bank, "query"):
                out = self.bank.query(task_id=task_id, query=prompt, k=5)  # type: ignore[attr-defined]
                mem["method"] = "query(task_id,query,k)"
                if isinstance(out, list):
                    mem["bank_snippets"] = out
                    mem["bank_hits"] = len(out)
                return mem
        except Exception:
            pass

        return mem

    # -----------------------------
    # Main handler
    # -----------------------------
    def handle(self, prompt: str, task_id: str = "default") -> AgentResult:
        response = self.llm.generate(prompt, system=self.system_prompt)

        # write
        write_meta = self._bank_write(task_id=task_id, prompt=prompt, text=response.text)

        # recall (always returns required keys)
        recall_meta = self._bank_recall(task_id=task_id, prompt=prompt)

        return AgentResult(
            agent_name=self.contract.name,
            text=response.text,
            meta={
                "model": response.model,
                "memory": {
                    **recall_meta,
                    "write": write_meta,
                },
            },
        )
