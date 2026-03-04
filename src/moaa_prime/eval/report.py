from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import List

from moaa_prime.eval.runner import EvalResult


def write_json_report(results: List[EvalResult], path: str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)

    avg_oracle = 0.0
    avg_entropy = 0.0
    avg_cost = 0.0
    avg_latency = 0.0
    if results:
        n = float(len(results))
        avg_oracle = sum(float(r.oracle_score) for r in results) / n
        avg_entropy = sum(float(r.routing_entropy) for r in results) / n
        avg_cost = sum(float(r.cost_proxy) for r in results) / n
        avg_latency = sum(float(r.latency_proxy) for r in results) / n

    payload = {
        "num_cases": len(results),
        "avg_oracle_score": avg_oracle,
        "avg_routing_entropy": avg_entropy,
        "avg_cost_proxy": avg_cost,
        "avg_latency_proxy": avg_latency,
        "results": [asdict(r) for r in results],
    }
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")
