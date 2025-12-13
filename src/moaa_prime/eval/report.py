from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import List

from moaa_prime.eval.runner import EvalResult


def write_json_report(results: List[EvalResult], path: str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "num_cases": len(results),
        "results": [asdict(r) for r in results],
    }
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")
