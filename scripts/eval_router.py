from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Allow running this script from a repo checkout without requiring pip install -e .
_SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if _SRC_DIR.exists() and str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from moaa_prime.core.app import MoAAPrime
from moaa_prime.eval.runner import EvalCase


def _load_cases() -> list[EvalCase]:
    path = Path("demos/demo_cases.json")
    if not path.exists():
        return [
            EvalCase(case_id="math_1", prompt="Solve: 2x + 3 = 7. Return only x.", mode="once"),
            EvalCase(case_id="code_1", prompt="Write Python: function add(a,b) returns a+b", mode="once"),
            EvalCase(
                case_id="swarm_1",
                prompt="Explain why 1/0 is undefined, then give a safe Python example.",
                mode="swarm",
            ),
        ]

    payload = json.loads(path.read_text(encoding="utf-8"))
    return [
        EvalCase(case_id=str(row["id"]), prompt=str(row["prompt"]), mode=str(row.get("mode", "once")))
        for row in payload.get("cases", [])
    ]


def main() -> int:
    seed = int(os.getenv("MOAA_ROUTER_EVAL_SEED") or "17")
    budget_mode = (os.getenv("MOAA_BUDGET_MODE") or "balanced").strip().lower()
    budget = {"mode": budget_mode}

    app_v2 = MoAAPrime(mode="v2", seed=seed)
    app_v3 = MoAAPrime(mode="v3", seed=seed)

    cases = _load_cases()
    rows = []

    v2_correct = 0
    v3_correct = 0

    v2_oracle_scores = []
    v3_oracle_scores = []

    v2_latencies = []
    v3_latencies = []
    v2_costs = []
    v3_costs = []

    for case in cases:
        once_v2 = app_v2.run_once(case.prompt, mode="v2", task_id=f"router-eval-{case.case_id}")
        once_v3 = app_v3.run_once(case.prompt, mode="v3", task_id=f"router-eval-{case.case_id}", budget=budget)

        swarm_v2 = app_v2.run_swarm(
            case.prompt,
            mode="v2",
            rounds=2,
            top_k=2,
            task_id=f"router-eval-{case.case_id}",
            run_id=f"router_eval_v2_{case.case_id}",
        )
        swarm_v3 = app_v3.run_swarm(
            case.prompt,
            mode="v3",
            rounds=2,
            top_k=2,
            cross_check=True,
            budget=budget,
            task_id=f"router-eval-{case.case_id}",
            run_id=f"router_eval_v3_{case.case_id}",
        )

        decision_v2 = str((once_v2.get("decision", {}) or {}).get("agent", ""))
        decision_v3 = str((once_v3.get("decision", {}) or {}).get("agent", ""))

        winner_v2 = str((swarm_v2.get("best", {}) or {}).get("agent", ""))
        winner_v3 = str((swarm_v3.get("best", {}) or {}).get("agent", ""))

        v2_correct += 1 if decision_v2 == winner_v2 else 0
        v3_correct += 1 if decision_v3 == winner_v3 else 0

        once_oracle_v2 = float((once_v2.get("oracle", {}) or {}).get("score", 0.0))
        once_oracle_v3 = float((once_v3.get("oracle", {}) or {}).get("score", 0.0))
        v2_oracle_scores.append(once_oracle_v2)
        v3_oracle_scores.append(once_oracle_v3)

        lat_v2 = float(swarm_v2.get("avg_latency_proxy", 0.0))
        lat_v3 = float(swarm_v3.get("avg_latency_proxy", 0.0))
        cost_v2 = float(swarm_v2.get("avg_cost_proxy", 0.0))
        cost_v3 = float(swarm_v3.get("avg_cost_proxy", 0.0))
        v2_latencies.append(lat_v2)
        v3_latencies.append(lat_v3)
        v2_costs.append(cost_v2)
        v3_costs.append(cost_v3)

        rows.append(
            {
                "case_id": case.case_id,
                "v2": {
                    "decision": decision_v2,
                    "winner": winner_v2,
                    "oracle_score": once_oracle_v2,
                    "avg_latency_proxy": lat_v2,
                    "avg_cost_proxy": cost_v2,
                },
                "v3": {
                    "decision": decision_v3,
                    "winner": winner_v3,
                    "oracle_score": once_oracle_v3,
                    "avg_latency_proxy": lat_v3,
                    "avg_cost_proxy": cost_v3,
                },
            }
        )

    n = float(max(1, len(cases)))

    v2_acc = float(v2_correct / n)
    v3_acc = float(v3_correct / n)

    avg_oracle_v2 = float(sum(v2_oracle_scores) / max(1.0, float(len(v2_oracle_scores))))
    avg_oracle_v3 = float(sum(v3_oracle_scores) / max(1.0, float(len(v3_oracle_scores))))

    avg_latency_v2 = float(sum(v2_latencies) / max(1.0, float(len(v2_latencies))))
    avg_latency_v3 = float(sum(v3_latencies) / max(1.0, float(len(v3_latencies))))
    avg_cost_v2 = float(sum(v2_costs) / max(1.0, float(len(v2_costs))))
    avg_cost_v3 = float(sum(v3_costs) / max(1.0, float(len(v3_costs))))

    report = {
        "seed": seed,
        "budget_mode": budget_mode,
        "num_cases": len(cases),
        "routing_accuracy": {
            "v2": v2_acc,
            "v3": v3_acc,
            "delta": float(v3_acc - v2_acc),
        },
        "oracle_score_gain": {
            "v2": avg_oracle_v2,
            "v3": avg_oracle_v3,
            "delta": float(avg_oracle_v3 - avg_oracle_v2),
        },
        "latency_efficiency": {
            "v2": avg_latency_v2,
            "v3": avg_latency_v3,
            "delta": float(avg_latency_v2 - avg_latency_v3),
            "improvement_ratio": float((avg_latency_v2 - avg_latency_v3) / max(1.0, avg_latency_v2)),
        },
        "cost_efficiency": {
            "v2": avg_cost_v2,
            "v3": avg_cost_v3,
            "delta": float(avg_cost_v2 - avg_cost_v3),
            "improvement_ratio": float((avg_cost_v2 - avg_cost_v3) / max(1.0, avg_cost_v2)),
        },
        "cases": rows,
    }

    Path("reports").mkdir(parents=True, exist_ok=True)
    out_path = Path("reports/eval_router.json")
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
