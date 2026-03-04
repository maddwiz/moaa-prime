from __future__ import annotations

from dataclasses import dataclass
import json
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
    def _lane_name(self) -> str:
        return str(getattr(self.contract, "name", "global") or "global")

    def _normalize_snippet(self, snippet: Any) -> str:
        if isinstance(snippet, str):
            return snippet

        # Preserve meaningful structure for MemoryItem-like objects.
        if hasattr(snippet, "task_id") and hasattr(snippet, "text"):
            payload = {
                "task_id": str(getattr(snippet, "task_id", "")),
                "text": str(getattr(snippet, "text", "")),
                "meta": getattr(snippet, "meta", None),
            }
            try:
                return json.dumps(payload, ensure_ascii=True, sort_keys=True, default=str)
            except Exception:
                return str(payload)

        try:
            return json.dumps(snippet, ensure_ascii=True, sort_keys=True, default=str)
        except Exception:
            return str(snippet)

    def _normalize_snippets(self, snippets: Any) -> list[str]:
        if snippets is None:
            return []
        if isinstance(snippets, (list, tuple, set)):
            return [self._normalize_snippet(snippet) for snippet in snippets]
        return [self._normalize_snippet(snippets)]

    def _memory_meta(self, *, task_id: str, recall_meta: dict[str, Any], write_meta: dict[str, Any]) -> dict[str, Any]:
        memory: dict[str, Any] = {
            "local_hits": recall_meta["local_hits"],
            "local_snippets": recall_meta["local_snippets"],
            "bank_hits": recall_meta["bank_hits"],
            "bank_snippets": recall_meta["bank_snippets"],
            "write": write_meta,
            "method": recall_meta["method"],
            "task_id": task_id,
        }
        if "global_text" in recall_meta:
            memory["global_text"] = str(recall_meta.get("global_text", ""))
        if "kl_like" in recall_meta:
            try:
                memory["kl_like"] = float(recall_meta["kl_like"])
            except (TypeError, ValueError):
                pass
        return memory

    def _bank_write(self, *, task_id: str, prompt: str, text: str) -> dict[str, Any]:
        meta: dict[str, Any] = {"task_id": task_id, "wrote": False, "method": None}

        if self.bank is None:
            return meta

        lane = self._lane_name()
        canonical_payload = {
            "task_id": "" if task_id is None else str(task_id),
            "text": "" if text is None else str(text),
            "lane": lane,
        }

        try:
            self.bank.write(
                task_id=canonical_payload["task_id"],
                text=canonical_payload["text"],
                lane=canonical_payload["lane"],
            )
            meta.update({"wrote": True, "method": "write(task_id,text,lane)"})
            return meta
        except Exception:
            pass

        try:
            self.bank.write(canonical_payload)
            meta.update({"wrote": True, "method": "write(payload)"})
            return meta
        except Exception:
            pass

        try:
            from moaa_prime.memory import MemoryItem

            self.bank.write(
                MemoryItem(
                    task_id=canonical_payload["task_id"],
                    text=canonical_payload["text"],
                    meta={"lane": canonical_payload["lane"]},
                )
            )
            meta.update({"wrote": True, "method": "write(MemoryItem)"})
            return meta
        except Exception:
            pass

        try:
            self.bank.add(canonical_payload)
            meta.update({"wrote": True, "method": "add(payload)"})
            return meta
        except Exception:
            pass

        try:
            self.bank.append(canonical_payload)
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

        method_parts: list[str] = []
        out: Any = None
        kl_like = 0.0
        kl_available = False
        global_text: Optional[str] = None

        try:
            out = self.bank.recall(task_id=task_id, query=prompt)
            method_parts.append("recall(task_id, query)")
        except Exception:
            try:
                out = self.bank.search(task_id=task_id, query=prompt)
                method_parts.append("search(task_id, query)")
            except Exception:
                method_parts.append("no-recall-method")

        bank_hits = 0
        bank_snippets: list[str] = []
        if isinstance(out, dict):
            raw_bank_snippets = out.get("snippets")
            if raw_bank_snippets is None:
                raw_bank_snippets = out.get("items") or []
            bank_snippets = self._normalize_snippets(raw_bank_snippets)
            try:
                bank_hits = int(out.get("bank_hits", len(bank_snippets)))
            except (TypeError, ValueError):
                bank_hits = len(bank_snippets)
            if "global_text" in out and out.get("global_text") is not None:
                global_text = str(out.get("global_text"))
            if "kl_like" in out:
                try:
                    kl_like = float(out.get("kl_like"))
                    kl_available = True
                except (TypeError, ValueError):
                    pass
        elif isinstance(out, list):
            bank_snippets = self._normalize_snippets(out)
            bank_hits = len(bank_snippets)
        elif out is not None:
            bank_snippets = self._normalize_snippets(out)
            bank_hits = len(bank_snippets)

        meta["bank_snippets"] = bank_snippets
        meta["bank_hits"] = bank_hits

        lane_recall: Any = None
        try:
            lane_recall = self.bank.lane_recall(
                lane=self._lane_name(),
                query=prompt,
                task_id=task_id,
                kl_like=kl_like,
            )
            method_parts.append("lane_recall(lane,query,task_id,kl_like)")
        except Exception:
            method_parts.append("no-lane-recall")

        local_hits = 0
        local_snippets: list[str] = []
        lane_global_text: Optional[str] = None
        if lane_recall is not None:
            if isinstance(lane_recall, dict):
                raw_local_snippets = lane_recall.get("snippets")
                if raw_local_snippets is None:
                    raw_local_snippets = lane_recall.get("items") or []
                local_snippets = self._normalize_snippets(raw_local_snippets)
                try:
                    local_hits = int(lane_recall.get("local_hits", len(local_snippets)))
                except (TypeError, ValueError):
                    local_hits = len(local_snippets)
                if lane_recall.get("global_text") is not None:
                    lane_global_text = str(lane_recall.get("global_text"))
            elif hasattr(lane_recall, "items"):
                raw_local_snippets = getattr(lane_recall, "items", []) or []
                local_snippets = self._normalize_snippets(raw_local_snippets)
                try:
                    local_hits = int(getattr(lane_recall, "local_hits", len(local_snippets)))
                except (TypeError, ValueError):
                    local_hits = len(local_snippets)
                if getattr(lane_recall, "global_text", None) is not None:
                    lane_global_text = str(getattr(lane_recall, "global_text"))
            elif isinstance(lane_recall, list):
                local_snippets = self._normalize_snippets(lane_recall)
                local_hits = len(local_snippets)
            else:
                local_snippets = self._normalize_snippets(lane_recall)
                local_hits = len(local_snippets)

        meta["local_snippets"] = local_snippets
        meta["local_hits"] = local_hits
        meta["method"] = " + ".join(method_parts)

        if lane_global_text is not None and lane_global_text.strip():
            meta["global_text"] = lane_global_text
        elif global_text is not None:
            meta["global_text"] = global_text
        if kl_available:
            meta["kl_like"] = float(kl_like)
        return meta

    def handle(self, prompt: str, task_id: str = "default") -> AgentResult:
        recall_meta = self._bank_recall(task_id=task_id, prompt=prompt)
        response = self.llm.generate(prompt, system=self.system_prompt)
        write_meta = self._bank_write(task_id=task_id, prompt=prompt, text=response.text)

        return AgentResult(
            agent_name=self.contract.name,
            text=response.text,
            meta={
                "model": response.model,
                "memory": self._memory_meta(task_id=task_id, recall_meta=recall_meta, write_meta=write_meta),
            },
        )
