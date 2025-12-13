from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from moaa_prime.contracts import Contract
from moaa_prime.memory import MemoryItem, ReasoningBank


@dataclass
class AgentResult:
    agent_name: str
    text: str
    meta: Optional[Dict[str, Any]] = None


class BaseAgent:
    def __init__(self, contract: Contract, bank: ReasoningBank | None = None) -> None:
        self.contract = contract
        self.bank = bank

    def _is_memory_write(self, p: str) -> bool:
        return p.startswith("remember:") or p.startswith("save:")

    def _is_memory_read(self, p: str) -> bool:
        return p.startswith("recall:") or p.startswith("what did we") or p.startswith("what was")

    def handle(self, prompt: str, task_id: str = "default") -> AgentResult:
        text = f"{self.contract.name} handled: {prompt}"
        meta: Dict[str, Any] = {"phase": "base-handle"}

        if self.bank is not None:
            p = prompt.strip().lower()

            # WRITE
            if self._is_memory_write(p):
                payload = prompt.split(":", 1)[1].strip()
                self.bank.write(
                    MemoryItem(
                        task_id=task_id,
                        text=payload,
                        meta={"lane": self.contract.name, "kind": "user_write"},
                    )
                )
                meta["memory"] = {"op": "write", "ok": True, "payload_len": len(payload)}
                return AgentResult(agent_name=self.contract.name, text="OK, remembered.", meta=meta)

            # READ
            if self._is_memory_read(p):
                out = self.bank.recall(query=prompt, task_id=task_id, top_k=5)
                meta["memory"] = {
                    "op": "recall",
                    "bank_hits": out.get("bank_hits", 0),
                    "kl_like": out.get("kl_like", 0.0),
                }
                recalled = out.get("global_text", "").strip()
                if recalled:
                    return AgentResult(agent_name=self.contract.name, text=recalled, meta=meta)
                return AgentResult(agent_name=self.contract.name, text="I don't have anything stored for that yet.", meta=meta)

        return AgentResult(agent_name=self.contract.name, text=text, meta=meta)
