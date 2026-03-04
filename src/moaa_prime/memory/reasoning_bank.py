from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Any

from .types import MemoryItem
from .episodic_lane import EpisodicLane
from .emre import _hash_embed, _cosine, build_sh_cos, entropy_proxy


@dataclass
class ReasoningBank:
    """
    Phase 5/6 global memory.
    - Per-agent lanes (local continuity)
    - Global store (cross-lane recall)
    - Phase 6 adds: kl_like + SH-COS text
    """
    items: List[MemoryItem] = field(default_factory=list)
    lanes: Dict[str, EpisodicLane] = field(default_factory=dict)

    def _lane(self, lane: str) -> EpisodicLane:
        if lane not in self.lanes:
            self.lanes[lane] = EpisodicLane(name=lane)
        return self.lanes[lane]

    def _append_item(self, item: MemoryItem, lane: str) -> None:
        lane_name = str(lane or "global")
        normalized_meta = dict(item.meta or {})
        normalized_meta["lane"] = lane_name
        normalized = MemoryItem(
            task_id=str(item.task_id),
            text=str(item.text),
            meta=normalized_meta,
        )
        self.items.append(normalized)
        self._lane(lane_name).append(normalized)

    def _payload_to_item(self, payload: dict[str, Any]) -> MemoryItem:
        task_id = payload.get("task_id")
        text = payload.get("text")
        if text is None and "content" in payload:
            text = payload.get("content")
        lane = payload.get("lane", "global")

        if task_id is None:
            raise ValueError("ReasoningBank.write requires 'task_id'.")
        if text is None:
            raise ValueError("ReasoningBank.write requires 'text' (or 'content').")

        meta: dict[str, Any] = {}
        if isinstance(payload.get("meta"), dict):
            meta.update(payload.get("meta") or {})
        for key, value in payload.items():
            if key in {"task_id", "text", "content", "lane", "meta"}:
                continue
            meta[str(key)] = value
        meta["lane"] = str(lane or "global")

        return MemoryItem(
            task_id=str(task_id),
            text=str(text),
            meta=meta,
        )

    # --- Backward compatible write API ---
    def write(self, *args: Any, **kwargs: Any) -> None:
        """
        Supports BOTH:
          write(MemoryItem(...))
          write(lane=..., task_id=..., content=...)
        """
        if args:
            if len(args) != 1:
                raise TypeError("ReasoningBank.write accepts at most one positional argument.")
            payload = args[0]
            if isinstance(payload, MemoryItem):
                lane = (payload.meta or {}).get("lane", "global")
                self._append_item(payload, str(lane))
                return
            if isinstance(payload, dict):
                item = self._payload_to_item(payload)
                lane = (item.meta or {}).get("lane", "global")
                self._append_item(item, str(lane))
                return
            raise TypeError("ReasoningBank.write positional payload must be MemoryItem or dict.")

        if kwargs:
            item = self._payload_to_item(dict(kwargs))
            lane = (item.meta or {}).get("lane", "global")
            self._append_item(item, str(lane))
            return

        raise ValueError("ReasoningBank.write requires MemoryItem or a payload with task_id/text.")

    def lane_recall(self, lane: str, query: str, task_id: str, kl_like: float = 0.0):
        return self._lane(lane).recall(query=query, task_id=task_id, kl_like=kl_like)

    def _rank(self, query: str, task_id: str, top_k: int = 5) -> List[MemoryItem]:
        qv = _hash_embed(f"{task_id}:{query}")
        scored: List[Tuple[float, MemoryItem]] = []
        for it in self.items:
            if it.task_id != task_id:
                continue
            sim = _cosine(_hash_embed(it.text), qv)
            scored.append((sim, it))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [it for _, it in scored[:top_k]]

    def recall(self, query: str, task_id: str, top_k: int = 5) -> Dict[str, Any]:
        hits = self._rank(query=query, task_id=task_id, top_k=top_k)
        sh = build_sh_cos([h.text for h in hits]) if hits else None

        ent = entropy_proxy(query)
        if not hits:
            kl_like = 1.0 if ent >= 0.85 else 0.6
        else:
            qv = _hash_embed(f"{task_id}:{query}")
            best = max(_cosine(_hash_embed(h.text), qv) for h in hits)
            kl_like = min(1.0, max(0.0, (1.0 - best) * (ent / 1.5)))

        return {
            "bank_hits": len(hits),
            "items": hits,
            "global_text": sh.as_text() if sh else "",
            "kl_like": float(kl_like),
        }
