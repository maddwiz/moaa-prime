from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Any, Optional

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

    # --- Backward compatible write API ---
    def write(self, *args: Any, **kwargs: Any) -> None:
        """
        Supports BOTH:
          write(MemoryItem(...))
          write(lane=..., task_id=..., content=...)
        """
        if args and isinstance(args[0], MemoryItem):
            item: MemoryItem = args[0]
            lane = (item.meta or {}).get("lane", "global")
            self.items.append(item)
            self._lane(str(lane)).append(item)
            return

        lane = str(kwargs.get("lane", "global"))
        task_id = str(kwargs.get("task_id", "default"))
        content = str(kwargs.get("content", ""))

        item = MemoryItem(task_id=task_id, text=content, meta={"lane": lane})
        self.items.append(item)
        self._lane(lane).append(item)

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
