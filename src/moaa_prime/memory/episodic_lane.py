from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Any


def _tok(s: str) -> List[str]:
    return [t.strip().lower() for t in s.replace("\n", " ").split() if t.strip()]


@dataclass(frozen=True)
class Episode:
    agent_name: str
    task_id: str
    text: str
    meta: dict | None = None


class EpisodicLane:
    """
    Per-agent, per-task episodic storage.

    Phase 5 baseline:
      - store Episode objects
      - retrieve by token overlap
      - filter by agent_name + task_id

    IMPORTANT:
      BaseAgent calls memory.add(agent_name=..., task_id=..., prompt=..., text=..., meta=...)
      so add() supports BOTH:
        (1) add(Episode(...))
        (2) add(agent_name=..., task_id=..., prompt=..., text=..., meta=...)
    """

    def __init__(self, max_items: int = 2000, lane_name: Optional[str] = None) -> None:
        self.max_items = int(max_items)
        self.lane_name = lane_name or ""
        self._items: List[Episode] = []

    def add(
        self,
        episode: Episode | None = None,
        *,
        agent_name: str | None = None,
        task_id: str | None = None,
        prompt: str | None = None,
        text: str | None = None,
        meta: dict | None = None,
        **extra: Any,
    ) -> None:
        # Mode 1: explicit Episode
        if episode is not None:
            if any(v is not None for v in (agent_name, task_id, prompt, text, meta)) or extra:
                raise TypeError("EpisodicLane.add(): pass either episode=Episode(...) OR keyword fields, not both.")
            e = episode
        else:
            # Mode 2: keyword fields (what BaseAgent uses)
            if extra:
                raise TypeError(f"EpisodicLane.add(): unexpected keyword(s): {sorted(extra.keys())}")
            if agent_name is None or task_id is None or text is None:
                raise TypeError("EpisodicLane.add(): agent_name, task_id, and text are required when not passing episode=...")

            # Put prompt into stored text so retrieval can match on it too.
            p = prompt or ""
            combined = f"prompt: {p}\ntext: {text}".strip()

            m = dict(meta or {})
            if prompt is not None:
                m.setdefault("prompt", prompt)

            e = Episode(agent_name=agent_name, task_id=task_id, text=combined, meta=m or None)

        self._items.append(e)
        overflow = len(self._items) - self.max_items
        if overflow > 0:
            del self._items[:overflow]

    def retrieve(self, prompt: str, agent_name: str, task_id: str, top_k: int = 3) -> List[Episode]:
        """
        Super simple retrieval: token overlap score.
        Filters by agent_name + task_id.
        """
        q = set(_tok(prompt))
        if not q:
            return []

        candidates = [e for e in self._items if e.agent_name == agent_name and e.task_id == task_id]
        scored = []
        for e in candidates:
            t = set(_tok(e.text))
            score = len(q.intersection(t))
            if score > 0:
                scored.append((score, e))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [e for _, e in scored[: max(1, int(top_k))]]
