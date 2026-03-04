from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping


def _safe_float(x: Any, default: float = 0.0) -> float:
    try:
        return float(x)
    except Exception:
        return float(default)


class TraceRecorder:
    """
    Stores run traces and appends router training records.

    Trace path:
      reports/traces/run_<id>.json

    Dataset path:
      datasets/router_training.jsonl
    """

    def __init__(
        self,
        *,
        trace_dir: str = "reports/traces",
        dataset_path: str = "datasets/router_training.jsonl",
    ) -> None:
        self.trace_dir = Path(trace_dir)
        self.dataset_path = Path(dataset_path)

    def _extract_router_choice(self, trace: Mapping[str, Any]) -> str:
        ranked = ((trace.get("router", {}) or {}).get("ranked", []) or [])
        if not ranked:
            return ""
        return str(ranked[0].get("agent", ""))

    def _extract_oracle_scores(self, candidates: list[Mapping[str, Any]]) -> Dict[str, float]:
        out: Dict[str, float] = {}
        for c in candidates:
            agent = str(c.get("agent", ""))
            if not agent:
                continue
            score = _safe_float(((c.get("oracle", {}) or {}).get("score", 0.0)))
            if agent not in out or score > out[agent]:
                out[agent] = score
        return out

    def _extract_agent_metrics(self, candidates: list[Mapping[str, Any]]) -> Dict[str, Dict[str, float]]:
        grouped: Dict[str, Dict[str, float]] = {}
        counts: Dict[str, int] = {}

        for c in candidates:
            agent = str(c.get("agent", ""))
            if not agent:
                continue

            row = grouped.setdefault(
                agent,
                {
                    "oracle_score": 0.0,
                    "latency": 0.0,
                    "cost": 0.0,
                    "confidence": 0.0,
                },
            )
            counts[agent] = counts.get(agent, 0) + 1

            row["oracle_score"] += _safe_float(((c.get("oracle", {}) or {}).get("score", 0.0)))
            row["latency"] += _safe_float(c.get("latency_proxy", 0.0))
            row["cost"] += _safe_float(c.get("cost_proxy", 0.0))
            row["confidence"] += _safe_float(c.get("confidence_proxy", 0.0), default=0.5)

        for agent, row in grouped.items():
            n = float(max(1, counts.get(agent, 1)))
            for key in ("oracle_score", "latency", "cost", "confidence"):
                row[key] = float(row[key] / n)
        return grouped

    def record(
        self,
        *,
        run_id: str,
        mode: str,
        task_id: str,
        prompt: str,
        trace: Mapping[str, Any],
        candidates: list[Mapping[str, Any]],
        best: Mapping[str, Any],
        contracts: Mapping[str, Mapping[str, Any]],
        budget_mode: str,
        avg_latency: float,
        avg_cost: float,
    ) -> Dict[str, str]:
        self.trace_dir.mkdir(parents=True, exist_ok=True)
        self.dataset_path.parent.mkdir(parents=True, exist_ok=True)

        router_choice = self._extract_router_choice(trace)
        oracle_scores = self._extract_oracle_scores(candidates)
        agent_metrics = self._extract_agent_metrics(candidates)
        winner = str(best.get("agent", ""))

        payload = {
            "run_id": str(run_id),
            "mode": str(mode),
            "task_id": str(task_id),
            "task": str(prompt),
            "agents": sorted(set(str(c.get("agent", "")) for c in candidates if str(c.get("agent", "")))),
            "router_choice": router_choice,
            "oracle_scores": oracle_scores,
            "winner": winner,
            "latency": _safe_float(avg_latency),
            "cost": _safe_float(avg_cost),
            "confidence": _safe_float((trace.get("final", {}) or {}).get("confidence", 0.0), default=0.5),
            "budget_mode": str(budget_mode),
            "agent_metrics": agent_metrics,
            "contracts": contracts,
        }

        trace_path = self.trace_dir / f"run_{run_id}.json"
        trace_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

        with self.dataset_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, sort_keys=True) + "\n")

        return {
            "trace_path": str(trace_path),
            "dataset_path": str(self.dataset_path),
        }
