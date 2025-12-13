from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass(frozen=True)
class AgentResult:
    agent_name: str
    text: str
    meta: Dict[str, Any] | None = None


class BaseAgent:
    """
    Base agent with minimal Phase 5 memory behavior.

    Memory contract we satisfy for tests:
      - On write: meta["memory"] exists
      - On read: meta["memory"] contains:
          local_hits, bank_hits (and we also include global_hits)
    """

    def __init__(self, contract: Any, bank: Any = None) -> None:
        self.contract = contract
        self.bank = bank

    def _is_memory_write(self, p: str) -> bool:
        return p.startswith("remember:")

    def _is_memory_read(self, p: str) -> bool:
        # Phase 5: heuristics to satisfy tests + be usable.
        if p.startswith("recall"):
            return True
        if p.startswith("remember what"):
            return True
        if "what was the answer" in p:
            return True
        if ("what was" in p or "what is" in p) and "answer" in p:
            return True
        return False

    def _entry_to_dict(self, entry: Any) -> Dict[str, Any]:
        # Supports dataclass-like objects or dicts
        if isinstance(entry, dict):
            return entry
        out: Dict[str, Any] = {}
        for k in ("lane", "task_id", "content", "text", "agent"):
            if hasattr(entry, k):
                out[k] = getattr(entry, k)
        return out

    def handle(self, prompt: str, task_id: str = "default") -> AgentResult:
        text = f"{self.contract.name} handled: {prompt}"
        meta: Dict[str, Any] = {"phase": "base-handle"}

        if self.bank is not None:
            p = prompt.strip().lower()

            # WRITE
            if self._is_memory_write(p):
                payload = prompt.split(":", 1)[1].strip()
                # Bank v1 expects: write(lane, task_id, content)
                self.bank.write(
                    lane=self.contract.name,
                    task_id=task_id,
                    content=payload,
                )
                meta["memory"] = {
                    "op": "write",
                    "task_id": task_id,
                    "agent": self.contract.name,
                    "text": payload,
                }

            # READ
            elif self._is_memory_read(p):
                # Local lane/task reads
                local_items: List[Any] = []
                if hasattr(self.bank, "read"):
                    try:
                        local_items = self.bank.read(lane=self.contract.name, task_id=task_id, k=5)
                    except TypeError:
                        # fallback if signature differs
                        local_items = self.bank.read(self.contract.name, task_id, 5)  # type: ignore

                # Global/bank reads (best-effort)
                bank_items: List[Any] = []
                if hasattr(self.bank, "search"):
                    try:
                        bank_items = self.bank.search(text=prompt, k=10)
                    except TypeError:
                        bank_items = self.bank.search(prompt, 10)  # type: ignore
                elif hasattr(self.bank, "read_global"):
                    try:
                        bank_items = self.bank.read_global(k=10)
                    except TypeError:
                        bank_items = self.bank.read_global(10)  # type: ignore

                items_dicts = [self._entry_to_dict(x) for x in (local_items or [])]

                meta["memory"] = {
                    "op": "read",
                    "task_id": task_id,
                    "agent": self.contract.name,
                    "items": items_dicts,
                    "local_hits": len(local_items or []),
                    # TEST WANTS THIS KEY:
                    "bank_hits": len(bank_items or []),
                    # Keep this too (won't hurt):
                    "global_hits": len(bank_items or []),
                }

        return AgentResult(agent_name=self.contract.name, text=text, meta=meta)
