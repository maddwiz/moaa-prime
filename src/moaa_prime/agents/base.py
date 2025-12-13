from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from moaa_prime.llm import LLMClient, make_llm_from_env


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
        self.llm = llm or make_llm_from_env()
        self.system_prompt = system_prompt

    # -----------------------------
    # Memory helpers (best-effort)
    # -----------------------------
    def _bank_write(self, *, task_id: str, prompt: str, text: str) -> dict[str, Any]:
        meta: dict[str, Any] = {"task_id": task_id, "wrote": False, "method": None}

        if self.bank is None:
            return meta

        payload = {"task_id": task_id, "agent": self.contract.name, "prompt": prompt, "text": text}

        try:
            self.bank.write(payload)
            meta.update({"wrote": True, "method": "write(payload)"})
            return meta
        except Exception:
            pass

        try:
            self.bank.add(payload)
            meta.update({"wrote": True, "method": "add(payload)"})
            return meta
        except Exception:
            pass

        try:
            self.bank.append(payload)
            meta.update({"wrote": True, "method": "append(payload)"})
            return meta
        except Exception:
            pass

        meta["method"] = "no-write-method"
        return meta

    def _bank_recall(self, *, task_id: str, prompt: str) -> dict[str, Any]:
        meta: dict[str, Any] = {
            "task_id": task_id,
            "local_hits": 0,
            "local_snippets": [],
            "bank_hits": 0,
            "bank_snippets": [],
            "method": None,
        }

        if self.bank is None:
            meta["method"] = "no-bank"
            return meta

        try:
            out = self.bank.recall(task_id=task_id, query=prompt)
            meta["method"] = "recall(task_id, query)"
            if isinstance(out, dict):
                # Try common keys
                snippets = out.get("snippets") or out.get("items") or []
                meta["bank_snippets"] = list(snippets)
                meta["bank_hits"] = len(meta["bank_snippets"])
            elif isinstance(out, list):
                meta["bank_snippets"] = out
                meta["bank_hits"] = len(out)
            return meta
        except Exception:
            pass

        try:
            out = self.bank.search(task_id=task_id, query=prompt)
            meta["method"] = "search(task_id, query)"
            if isinstance(out, list):
                meta["bank_snippets"] = out
                meta["bank_hits"] = len(out)
            return meta
        except Exception:
            pass

        meta["method"] = "no-recall-method"
        return meta

    def handle(self, prompt: str, task_id: str = "default") -> AgentResult:
        response = self.llm.generate(prompt, system=self.system_prompt)

        write_meta = self._bank_write(task_id=task_id, prompt=prompt, text=response.text)
        recall_meta = self._bank_recall(task_id=task_id, prompt=prompt)

        return AgentResult(
            agent_name=self.contract.name,
            text=response.text,
            meta={
                "model": response.model,
                "memory": {
                    "local_hits": recall_meta["local_hits"],
                    "local_snippets": recall_meta["local_snippets"],
                    "bank_hits": recall_meta["bank_hits"],
                    "bank_snippets": recall_meta["bank_snippets"],
                    "write": write_meta,
                    "method": recall_meta["method"],
                    "task_id": task_id,
                },
            },
        )
