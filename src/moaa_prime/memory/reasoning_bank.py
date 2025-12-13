from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass(frozen=True)
class MemoryEntry:
    lane: str
    task_id: str
    content: str


class ReasoningBank:
    """
    Phase 5 (Option 2): per-agent lanes + global bank.
    Minimal v1:
      - write(lane, task_id, content)
      - read(lane, task_id, k)
      - search(text, k) (simple substring)
    """

    def __init__(self) -> None:
        # lane -> task_id -> entries
        self._lanes: Dict[str, Dict[str, List[MemoryEntry]]] = {}
        # global list (append-only)
        self._global: List[MemoryEntry] = []

    def write(self, lane: str, task_id: str, content: str) -> None:
        entry = MemoryEntry(lane=lane, task_id=task_id, content=content)
        self._global.append(entry)
        self._lanes.setdefault(lane, {}).setdefault(task_id, []).append(entry)

    def read(self, lane: str, task_id: str, k: int = 5) -> List[MemoryEntry]:
        entries = self._lanes.get(lane, {}).get(task_id, [])
        if k <= 0:
            return []
        return entries[-k:]

    def read_global(self, k: int = 10) -> List[MemoryEntry]:
        if k <= 0:
            return []
        return self._global[-k:]

    def search(self, text: str, k: int = 10, lane: Optional[str] = None) -> List[MemoryEntry]:
        """
        Very simple search for now: substring match over content.
        """
        if not text:
            return []

        haystack = self._global if lane is None else [
            e for e in self._global if e.lane == lane
        ]

        hits = [e for e in reversed(haystack) if text.lower() in e.content.lower()]
        return hits[: max(0, k)]
