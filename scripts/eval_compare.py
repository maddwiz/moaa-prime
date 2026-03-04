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
from moaa_prime.eval.runner import EvalCase, EvalRunner


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
    cases = [
        EvalCase(case_id=str(row["id"]), prompt=str(row["prompt"]), mode=str(row.get("mode", "once")))
        for row in payload.get("cases", [])
    ]

    slice_n = int(os.getenv("MOAA_EVAL_SLICE") or "0")
    if slice_n > 0:
        return cases[:slice_n]
    return cases


def _aggregate(results):
    if not results:
        return {
            "avg_oracle_score": 0.0,
            "routing_entropy": 0.0,
            "avg_cost_proxy": 0.0,
            "avg_latency_proxy": 0.0,
        }

    n = float(len(results))
    return {
        "avg_oracle_score": float(sum(r.oracle_score for r in results) / n),
        "routing_entropy": float(sum(r.routing_entropy for r in results) / n),
        "avg_cost_proxy": float(sum(r.cost_proxy for r in results) / n),
        "avg_latency_proxy": float(sum(r.latency_proxy for r in results) / n),
    }


def _delta(v1: float, v2: float) -> float:
    return float(v2 - v1)


def _count_passed(per_case: list[dict[str, object]]) -> int:
    return int(sum(1 for row in per_case if float(row.get("v2_minus_v1", 0.0)) >= 0.0))


def main() -> int:
    seed = int(os.getenv("MOAA_EVAL_COMPARE_SEED") or "11")
    cases = _load_cases()

    runner_v1 = EvalRunner(model_mode="v1", seed=seed)
    runner_v2 = EvalRunner(model_mode="v2", seed=seed)

    results_v1 = runner_v1.run(cases)
    results_v2 = runner_v2.run(cases)

    agg_v1 = _aggregate(results_v1)
    agg_v2 = _aggregate(results_v2)

    wins = 0
    per_case = []
    for left, right in zip(results_v1, results_v2):
        if right.oracle_score > left.oracle_score:
            wins += 1
        per_case.append(
            {
                "case_id": left.case_id,
                "mode": left.mode,
                "v1_oracle": float(left.oracle_score),
                "v2_oracle": float(right.oracle_score),
                "v2_minus_v1": float(right.oracle_score - left.oracle_score),
            }
        )

    win_rate = float(wins / max(1, len(per_case)))
    passed = _count_passed(per_case)
    counts = {
        "num_cases": int(len(cases)),
        "scored_cases": int(len(per_case)),
        "passed": int(passed),
    }

    # Emit deterministic trace files for one representative swarm prompt in both modes.
    trace_paths = []
    swarm_case = next((c for c in cases if c.mode == "swarm"), None)
    if swarm_case is not None:
        app_v1 = MoAAPrime(mode="v1", seed=seed)
        app_v2 = MoAAPrime(mode="v2", seed=seed)

        out_v1 = app_v1.run_swarm(swarm_case.prompt, task_id="eval-compare", mode="v1", run_id=f"compare_v1_{seed}")
        out_v2 = app_v2.run_swarm(swarm_case.prompt, task_id="eval-compare", mode="v2", run_id=f"compare_v2_{seed}")

        if out_v1.get("trace_path"):
            trace_paths.append(str(out_v1["trace_path"]))
        if out_v2.get("trace_path"):
            trace_paths.append(str(out_v2["trace_path"]))

    report = {
        "suite": "eval_compare",
        "schema_version": "1.1",
        "seed": seed,
        "counts": counts,
        "num_cases": int(counts["num_cases"]),
        "scored_cases": int(counts["scored_cases"]),
        "passed": int(counts["passed"]),
        "pass_rate": float(passed / max(1, len(per_case))),
        "summary": {
            "counts": counts,
            "metrics": {
                "avg_oracle_score_v1": agg_v1["avg_oracle_score"],
                "avg_oracle_score_v2": agg_v2["avg_oracle_score"],
                "avg_oracle_score_delta": _delta(agg_v1["avg_oracle_score"], agg_v2["avg_oracle_score"]),
                "win_rate_v2_over_v1": win_rate,
                "routing_entropy_v1": agg_v1["routing_entropy"],
                "routing_entropy_v2": agg_v2["routing_entropy"],
                "routing_entropy_delta": _delta(agg_v1["routing_entropy"], agg_v2["routing_entropy"]),
                "avg_cost_proxy_v1": agg_v1["avg_cost_proxy"],
                "avg_cost_proxy_v2": agg_v2["avg_cost_proxy"],
                "avg_cost_proxy_delta": _delta(agg_v1["avg_cost_proxy"], agg_v2["avg_cost_proxy"]),
                "avg_latency_proxy_v1": agg_v1["avg_latency_proxy"],
                "avg_latency_proxy_v2": agg_v2["avg_latency_proxy"],
                "avg_latency_proxy_delta": _delta(agg_v1["avg_latency_proxy"], agg_v2["avg_latency_proxy"]),
            },
        },
        "avg_oracle_score": {
            "v1": agg_v1["avg_oracle_score"],
            "v2": agg_v2["avg_oracle_score"],
            "delta": _delta(agg_v1["avg_oracle_score"], agg_v2["avg_oracle_score"]),
        },
        "win_rate_v2_over_v1": win_rate,
        "routing_entropy": {
            "v1": agg_v1["routing_entropy"],
            "v2": agg_v2["routing_entropy"],
            "delta": _delta(agg_v1["routing_entropy"], agg_v2["routing_entropy"]),
        },
        "avg_cost_proxy": {
            "v1": agg_v1["avg_cost_proxy"],
            "v2": agg_v2["avg_cost_proxy"],
            "delta": _delta(agg_v1["avg_cost_proxy"], agg_v2["avg_cost_proxy"]),
        },
        "avg_latency_proxy": {
            "v1": agg_v1["avg_latency_proxy"],
            "v2": agg_v2["avg_latency_proxy"],
            "delta": _delta(agg_v1["avg_latency_proxy"], agg_v2["avg_latency_proxy"]),
        },
        "cases": per_case,
        "trace_paths": trace_paths,
    }

    Path("reports").mkdir(parents=True, exist_ok=True)
    Path("reports/eval_compare.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("Wrote reports/eval_compare.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
