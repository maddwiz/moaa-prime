from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, List

from moaa_prime.contracts import Contract

try:
    from moaa_prime.memory import ReasoningBank
except Exception:  # pragma: no cover
    ReasoningBank = None  # type: ignore


@dataclass(frozen=True)
class AgentResult:
    agent_name: str
    text: str
    meta: Dict[str, Any] | None = None


class BaseAgent:
    """
    Base agent with Phase 5 memory schema preserved,
    while Phase 6 (E-MRE) enriches it (kl_like + SH-COS).
    """

    def __init__(self, contract: Contract, bank: Optional[ReasoningBank] = None) -> None:
        self.contract = contract
        self.bank = bank

    def _is_memory_write(self, p: str) -> bool:
        return p.startswith("remember:")

    def _is_memory_read(self, p: str) -> bool:
        # Match earlier behavior + Phase 5 tests
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
        if isinstance(entry, dict):
            return entry
        out: Dict[str, Any] = {}
        for k in ("lane", "task_id", "content", "text"):
            if hasattr(entry, k):
                out[k] = getattr(entry, k)
        # normalize "content" vs "text"
        if "content" not in out and "text" in out:
            out["content"] = out["text"]
        return out

    def handle(self, prompt: str, task_id: str = "default") -> AgentResult:
        meta: Dict[str, Any] = {"phase": "base-handle"}
        p = (prompt or "").strip()
        pl = p.lower()

        # If no bank, just echo
        if self.bank is None:
            text = f"{self.contract.name} handled: {prompt}"
            return AgentResult(agent_name=self.contract.name, text=text, meta=meta)

        # WRITE
        if self._is_memory_write(pl):
            payload = p.split(":", 1)[1].strip()
            self.bank.write(lane=self.contract.name, task_id=task_id, content=payload)
            meta["memory"] = {
                "op": "write",
                "task_id": task_id,
                "agent": self.contract.name,
                "text": payload,
            }
            return AgentResult(agent_name=self.contract.name, text="OK, remembered.", meta=meta)

        # READ
        if self._is_memory_read(pl):
            bank_out = self.bank.recall(query=p, task_id=task_id, top_k=5)
            kl_like = float(bank_out.get("kl_like", 0.0))

            lane_res = self.bank.lane_recall(
                lane=self.contract.name,
                query=p,
                task_id=task_id,
                kl_like=kl_like,
            )

            local_items = [self._entry_to_dict(it) for it in lane_res.items]
            bank_items = [self._entry_to_dict(it) for it in (bank_out.get("items", []) or [])]

            meta["memory"] = {
                "op": "read",
                "task_id": task_id,
                "agent": self.contract.name,
                # Phase 5 required fields:
                "local_hits": int(getattr(lane_res, "local_hits", 0)),
                "bank_hits": int(bank_out.get("bank_hits", 0)),
                "global_hits": int(getattr(lane_res, "global_hits", 0)),
                "items": local_items,
                # Phase 6 enrichments:
                "bank_items": bank_items,
                "global_text": str(getattr(lane_res, "global_text", "") or bank_out.get("global_text", "")),
                "kl_like": kl_like,
            }

            text = f"{self.contract.name} recall: {len(local_items)} local, {len(bank_items)} bank."
            return AgentResult(agent_name=self.contract.name, text=text, meta=meta)

        # Default behavior
        text = f"{self.contract.name} handled: {prompt}"
        return AgentResult(agent_name=self.contract.name, text=text, meta=meta)
