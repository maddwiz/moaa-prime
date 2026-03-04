from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from typing import Any


def _default(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    if hasattr(value, "__dict__"):
        return value.__dict__
    return str(value)


def dumps_pretty(payload: Any) -> str:
    return json.dumps(payload, indent=2, default=_default)
