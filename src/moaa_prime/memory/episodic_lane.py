from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from .types import MemoryItem, RecallResult
from .emre import (
    build_sh_cos,
    curiosity_bump_order,
    entropy_proxy,
    gfo_keep_mask,
)


@dataclass
class EpisodicLane:
    """
    Phase 6: E-MRE v1 lane.
    Stores MemoryItems and uses:
      - AEDMC-lite: adaptive k based on entropy proxy
      - SH-COS: multi-level summary injected into recall context
      - GFO: anchor-guided pruning to prevent unbounded growth
    """
    name: str
    items: List[MemoryItem] = field(default_factory=list)

    # working set (kept raw) + retention knobs
    working_max: int = 64
    keep_top_frac: float = 0.85
    min_keep: int = 16

    def append(self, item: MemoryItem) -> None:
        self.items.append(item)
        # GFO prune when we grow too big
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
        """
        Returns:
          - items: selected memory items (local)
          - global_hits: SH-COS text (as a string) so app can surface it
        """
        # Filter to task_id first (simple v1)
        candidates = [it for it in self.items if it.task_id == task_id]
        if not candidates:
            return RecallResult(local_hits=0, bank_hits=0, global_hits=0, items=[], global_text="")

        # AEDMC-lite: pick k from entropy, with curiosity bump
        ent = entropy_proxy(query)
        k = curiosity_bump_order(entropy=ent, kl_like=kl_like)

        # Keep last k items (Markov-ish)
        chosen = candidates[-k:]

        sh = build_sh_cos([it.text for it in chosen])

        return RecallResult(
            local_hits=len(chosen),
            bank_hits=0,
            global_hits=1,
            items=chosen,
            global_text=sh.as_text(),
        )
