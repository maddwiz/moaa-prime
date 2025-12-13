from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class MemoryItem:
    task_id: str
    text: str
    meta: Optional[Dict[str, Any]] = None


@dataclass
class RecallResult:
    local_hits: int
    bank_hits: int
    global_hits: int
    items: List[MemoryItem]
    global_text: str = ""
