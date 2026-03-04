from __future__ import annotations

from typing import Dict, List, Sequence


def _dominates(a: Dict[str, float], b: Dict[str, float]) -> bool:
    """
    Pareto dominance where higher score/confidence and lower latency/cost are better.
    """
    better_or_equal = (
        float(a.get("score", 0.0)) >= float(b.get("score", 0.0))
        and float(a.get("confidence", 0.0)) >= float(b.get("confidence", 0.0))
        and float(a.get("latency", 0.0)) <= float(b.get("latency", 0.0))
        and float(a.get("cost", 0.0)) <= float(b.get("cost", 0.0))
    )
    strictly_better = (
        float(a.get("score", 0.0)) > float(b.get("score", 0.0))
        or float(a.get("confidence", 0.0)) > float(b.get("confidence", 0.0))
        or float(a.get("latency", 0.0)) < float(b.get("latency", 0.0))
        or float(a.get("cost", 0.0)) < float(b.get("cost", 0.0))
    )
    return bool(better_or_equal and strictly_better)


def pareto_frontier(points: Sequence[Dict[str, float]]) -> List[Dict[str, float]]:
    frontier: List[Dict[str, float]] = []
    for i, p in enumerate(points):
        dominated = False
        for j, q in enumerate(points):
            if i == j:
                continue
            if _dominates(q, p):
                dominated = True
                break
        if not dominated:
            frontier.append(dict(p))

    frontier.sort(
        key=lambda p: (
            float(p.get("score", 0.0)),
            float(p.get("confidence", 0.0)),
            -float(p.get("latency", 0.0)),
            -float(p.get("cost", 0.0)),
            str(p.get("id", "")),
        ),
        reverse=True,
    )
    return frontier
