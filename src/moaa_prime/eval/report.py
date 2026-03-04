from __future__ import annotations

import json
from dataclasses import asdict
import math
from pathlib import Path
from typing import List

from moaa_prime.eval.runner import EvalResult


def _safe_float(value: object, *, default: float = 0.0) -> float:
    try:
        num = float(value)
    except (TypeError, ValueError):
        return float(default)
    if not math.isfinite(num):
        return float(default)
    return float(num)


def write_json_report(results: List[EvalResult], path: str, *, pass_threshold: float = 0.75) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)

    oracle_scores = [_safe_float(r.oracle_score) for r in results]
    entropies = [_safe_float(r.routing_entropy) for r in results]
    costs = [_safe_float(r.cost_proxy) for r in results]
    latencies = [_safe_float(r.latency_proxy) for r in results]

    scored_cases = int(len(oracle_scores))
    passed = int(sum(1 for score in oracle_scores if score >= pass_threshold))
    pass_rate = float(passed / scored_cases) if scored_cases > 0 else 0.0

    avg_oracle = float(sum(oracle_scores) / scored_cases) if scored_cases > 0 else 0.0
    avg_entropy = float(sum(entropies) / max(1, len(entropies)))
    avg_cost = float(sum(costs) / max(1, len(costs)))
    avg_latency = float(sum(latencies) / max(1, len(latencies)))

    counts = {
        "num_cases": int(len(results)),
        "scored_cases": scored_cases,
        "passed": passed,
    }
    metrics = {
        "pass_threshold": float(_safe_float(pass_threshold)),
        "pass_rate": float(pass_rate),
        "avg_oracle_score": float(avg_oracle),
        "avg_routing_entropy": float(avg_entropy),
        "avg_cost_proxy": float(avg_cost),
        "avg_latency_proxy": float(avg_latency),
    }

    payload = {
        "schema_version": "1.1",
        "counts": counts,
        "summary": {
            "counts": counts,
            "metrics": metrics,
        },
        # Legacy top-level numeric fields remain for compatibility.
        "num_cases": int(counts["num_cases"]),
        "scored_cases": int(counts["scored_cases"]),
        "passed": int(counts["passed"]),
        "pass_rate": float(metrics["pass_rate"]),
        "avg_oracle_score": float(metrics["avg_oracle_score"]),
        "avg_routing_entropy": float(metrics["avg_routing_entropy"]),
        "avg_cost_proxy": float(metrics["avg_cost_proxy"]),
        "avg_latency_proxy": float(metrics["avg_latency_proxy"]),
        "results": [asdict(r) for r in results],
    }
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")
