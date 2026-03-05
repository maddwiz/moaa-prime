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


DEFAULT_MIN_CASES = 100


def _safe_int(value: object, *, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _env_min_cases(name: str, *, default: int, minimum: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        value = int(default)
    else:
        value = _safe_int(raw, default=default)
    return int(max(int(minimum), int(value)))


def _expand_eval_cases(cases: list[EvalCase], *, min_cases: int) -> list[EvalCase]:
    if not cases:
        return []
    if int(min_cases) <= len(cases):
        return list(cases)

    expanded: list[EvalCase] = []
    base_count = len(cases)
    for idx in range(int(min_cases)):
        base = cases[idx % base_count]
        case_id = base.case_id if idx < base_count else f"{base.case_id}__rep{idx:03d}"
        expanded.append(EvalCase(case_id=case_id, prompt=base.prompt, mode=base.mode))
    return expanded


def _non_regression_pass(v2_value: float, v3_value: float, *, tolerance: float) -> bool:
    return float(v3_value - v2_value) >= (-abs(float(tolerance)))


def _validated_counts(*, num_cases: int, scored_cases: int, passed: int) -> dict[str, int]:
    num = max(0, int(num_cases))
    scored = max(0, min(num, int(scored_cases)))
    passed_clamped = max(0, min(scored, int(passed)))
    return {
        "num_cases": int(num),
        "scored_cases": int(scored),
        "passed": int(passed_clamped),
    }


def _load_cases() -> list[EvalCase]:
    cases_path = os.getenv("MOAA_ROUTER_EVAL_CASES_PATH")
    path = Path(cases_path) if cases_path else Path("demos/demo_cases.json")
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
    non_regression_tolerance = float(os.getenv("MOAA_ROUTER_NON_REGRESSION_TOL") or "0.000001")
    report_path = Path(os.getenv("MOAA_ROUTER_EVAL_REPORT_PATH") or "reports/eval_router.json")
    budget = {"mode": budget_mode}

    app_v2 = MoAAPrime(mode="v2", seed=seed)
    app_v3 = MoAAPrime(mode="v3", seed=seed)

    cases = _load_cases()
    explicit_cases_path = os.getenv("MOAA_ROUTER_EVAL_CASES_PATH")
    explicit_min_env = os.getenv("MOAA_ROUTER_EVAL_MIN_CASES")
    if explicit_cases_path and explicit_min_env is None:
        min_cases = int(len(cases))
    else:
        min_cases = _env_min_cases(
            "MOAA_ROUTER_EVAL_MIN_CASES",
            default=DEFAULT_MIN_CASES,
            minimum=len(cases),
        )
    cases = _expand_eval_cases(cases, min_cases=min_cases)
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
    routing_delta = float(v3_acc - v2_acc)
    oracle_delta = float(avg_oracle_v3 - avg_oracle_v2)
    routing_non_regression = _non_regression_pass(v2_acc, v3_acc, tolerance=non_regression_tolerance)
    oracle_non_regression = _non_regression_pass(avg_oracle_v2, avg_oracle_v3, tolerance=non_regression_tolerance)
    counts = _validated_counts(
        num_cases=int(len(cases)),
        scored_cases=int(len(rows)),
        passed=int(
            sum(
                1
                for row in rows
                if float((row.get("v3", {}) or {}).get("oracle_score", 0.0))
                >= float((row.get("v2", {}) or {}).get("oracle_score", 0.0))
            )
        ),
    )

    report = {
        "suite": "eval_router",
        "schema_version": "1.1",
        "seed": seed,
        "budget_mode": budget_mode,
        "non_regression_tolerance": non_regression_tolerance,
        "counts": counts,
        "num_cases": int(counts["num_cases"]),
        "scored_cases": int(counts["scored_cases"]),
        "passed": int(counts["passed"]),
        "pass_rate": float(counts["passed"] / max(1, counts["scored_cases"])),
        "routing_accuracy": {
            "v2": v2_acc,
            "v3": v3_acc,
            "delta": routing_delta,
        },
        "oracle_score_gain": {
            "v2": avg_oracle_v2,
            "v3": avg_oracle_v3,
            "delta": oracle_delta,
        },
        "non_regression_vs_v2": {
            "routing_accuracy": {
                "passed": bool(routing_non_regression),
                "delta": routing_delta,
            },
            "oracle_score_gain": {
                "passed": bool(oracle_non_regression),
                "delta": oracle_delta,
            },
            "passed": bool(routing_non_regression and oracle_non_regression),
        },
        "summary": {
            "counts": counts,
            "metrics": {
                "routing_accuracy_v2": v2_acc,
                "routing_accuracy_v3": v3_acc,
                "routing_accuracy_delta": routing_delta,
                "oracle_score_gain_v2": avg_oracle_v2,
                "oracle_score_gain_v3": avg_oracle_v3,
                "oracle_score_gain_delta": oracle_delta,
                "latency_efficiency_v2": avg_latency_v2,
                "latency_efficiency_v3": avg_latency_v3,
                "latency_efficiency_delta": float(avg_latency_v2 - avg_latency_v3),
                "cost_efficiency_v2": avg_cost_v2,
                "cost_efficiency_v3": avg_cost_v3,
                "cost_efficiency_delta": float(avg_cost_v2 - avg_cost_v3),
                "non_regression_passed": bool(routing_non_regression and oracle_non_regression),
            },
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

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Wrote {report_path}")
    print(
        "non_regression_vs_v2:"
        f" routing_accuracy={'PASS' if routing_non_regression else 'FAIL'}"
        f" ({routing_delta:+.6f}),"
        f" oracle_score_gain={'PASS' if oracle_non_regression else 'FAIL'}"
        f" ({oracle_delta:+.6f})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
