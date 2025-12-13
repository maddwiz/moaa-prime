from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from .types import MemoryItem
from .emre import _hash_embed, _cosine, build_sh_cos, entropy_proxy


@dataclass
class ReasoningBank:
    """
    Global shared store (Phase 5/6).
    Phase 6 adds:
      - deterministic embedding similarity
      - returns SH-COS of top hits
      - provides a simple curiosity signal (kl_like proxy) to lanes
    """
    items: List[MemoryItem] = field(default_factory=list)

    def write(self, item: MemoryItem) -> None:
        self.items.append(item)

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

    def recall(self, query: str, task_id: str, top_k: int = 5) -> Dict:
        hits = self._rank(query=query, task_id=task_id, top_k=top_k)
        sh = build_sh_cos([h.text for h in hits]) if hits else None

        # "kl_like" proxy:
        # higher when query entropy is high AND bank has low similarity hits
        ent = entropy_proxy(query)
        if not hits:
            kl_like = 1.0 if ent >= 0.85 else 0.6
        else:
            qv = _hash_embed(f"{task_id}:{query}")
            best = max(_cosine(_hash_embed(h.text), qv) for h in hits)
            # invert similarity to act like "distance from known memory"
            kl_like = min(1.0, max(0.0, (1.0 - best) * (ent / 1.5)))

        return {
            "bank_hits": len(hits),
            "items": hits,
            "global_text": sh.as_text() if sh else "",
            "kl_like": float(kl_like),
        }
