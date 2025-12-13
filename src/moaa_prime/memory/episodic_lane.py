from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from .types import MemoryItem, RecallResult
from .emre import (
    build_sh_cos,
    choose_markov_order,
    curiosity_bump_order,
    entropy_proxy,
    gfo_keep_mask,
)


@dataclass
class EpisodicLane:
    """
    Phase 6: E-MRE v1 lane.
    - AEDMC-lite (entropy -> k)
    - Curiosity bump (Grok riff)
    - SH-COS text returned as global_text
    - GFO pruning when lane grows too large
    """
    name: str
    items: List[MemoryItem] = field(default_factory=list)

    working_max: int = 64
    keep_top_frac: float = 0.85
    min_keep: int = 16

    def append(self, item: MemoryItem) -> None:
        self.items.append(item)

        if len(self.items) > self.working_max:
            anchor = f"{item.task_id}:{self.name}"
            segs = [it.text for it in self.items]
            mask = gfo_keep_mask(
                segs,
                task_anchor=anchor,
                keep_top_frac=self.keep_top_frac,
                min_keep=self.min_keep,
            )
            self.items = [it for it, keep in zip(self.items, mask) if keep]

    def recall(self, query: str, task_id: str, kl_like: float = 0.0) -> RecallResult:
        candidates = [it for it in self.items if it.task_id == task_id]
        if not candidates:
            return RecallResult(local_hits=0, bank_hits=0, global_hits=0, items=[], global_text="")

        ent = entropy_proxy(query)
        base_k = choose_markov_order(ent)
        k = curiosity_bump_order(entropy=ent, base_k=base_k, kl_like=kl_like)

        # v1: take most recent k for this task_id
        chosen = candidates[-k:]

        sh = build_sh_cos([it.text for it in chosen])

        return RecallResult(
            local_hits=len(chosen),
            bank_hits=0,
            global_hits=1 if sh.as_text().strip() else 0,
            items=chosen,
            global_text=sh.as_text(),
        )
