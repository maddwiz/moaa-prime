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


CASE_PROMPTS = [
    {"id": "math_linear", "prompt": "Solve 2x + 3 = 7"},
    {"id": "code_add", "prompt": "Write Python: function add(a,b) returns a+b"},
    {"id": "safety_reasoning", "prompt": "Explain why 1/0 is undefined with a safe Python snippet"},
    {"id": "traceback_fix", "prompt": "Fix this traceback TypeError in my function"},
    {"id": "algebra_quadratic", "prompt": "Solve x^2 - 7*x + 10 = 0 for x"},
    {"id": "general_policy", "prompt": "Give a concise plan for debugging a failing script"},
]


def _oracle_score(payload: dict[str, object]) -> float:
    best = payload.get("best", {}) or {}
    if not isinstance(best, dict):
        return 0.0
    oracle = best.get("oracle", {}) or {}
    if not isinstance(oracle, dict):
        return 0.0
    try:
        return float(oracle.get("score", 0.0))
    except (TypeError, ValueError):
        return 0.0


def _dual_gate_block(payload: dict[str, object]) -> dict[str, object]:
    trace = payload.get("trace", {}) or {}
    if not isinstance(trace, dict):
        return {}
    swarm = trace.get("swarm", {}) or {}
    if not isinstance(swarm, dict):
        return {}
    dual_gate = swarm.get("dual_gate", {}) or {}
    if not isinstance(dual_gate, dict):
        return {}
    return dual_gate


def _pass_rate(values: list[bool]) -> float:
    if not values:
        return 0.0
    return float(sum(1 for value in values if value) / len(values))


def main() -> int:
    seed = int(os.getenv("MOAA_PR4_EVAL_SEED") or "29")
    pass_threshold = 0.70

    rows = []
    baseline_scores: list[float] = []
    gated_scores: list[float] = []
    baseline_passes: list[bool] = []
    gated_passes: list[bool] = []
    gate_triggered: list[bool] = []

    for idx, case in enumerate(CASE_PROMPTS):
        baseline_app = MoAAPrime(mode="v3", seed=seed)
        gated_app = MoAAPrime(mode="v3", seed=seed)

        baseline = baseline_app.run_swarm(
            str(case["prompt"]),
            task_id=f"pr4-baseline-{idx}",
            mode="v3",
            rounds=1,
            top_k=2,
            dual_gate=False,
        )
        gated = gated_app.run_swarm(
            str(case["prompt"]),
            task_id=f"pr4-gated-{idx}",
            mode="v3",
            rounds=1,
            top_k=2,
            dual_gate=True,
            dual_gate_config={"high_ambiguity_threshold": 0.0},
        )

        baseline_score = _oracle_score(baseline)
        gated_score = _oracle_score(gated)
        baseline_pass = baseline_score >= pass_threshold
        gated_pass = gated_score >= pass_threshold

        dual_gate = _dual_gate_block(gated)
        triggered = bool(dual_gate.get("triggered", False))

        baseline_scores.append(baseline_score)
        gated_scores.append(gated_score)
        baseline_passes.append(baseline_pass)
        gated_passes.append(gated_pass)
        gate_triggered.append(triggered)

        rows.append(
            {
                "case_id": str(case["id"]),
                "prompt": str(case["prompt"]),
                "baseline": {
                    "oracle_score": baseline_score,
                    "pass": baseline_pass,
                    "winner_agent": str((baseline.get("best", {}) or {}).get("agent", "")),
                },
                "dual_gated": {
                    "oracle_score": gated_score,
                    "pass": gated_pass,
                    "winner_agent": str((gated.get("best", {}) or {}).get("agent", "")),
                    "triggered": triggered,
                    "reasons": list(dual_gate.get("reasons", []) or []),
                    "selector_rule": str((dual_gate.get("selector", {}) or {}).get("rule", "")),
                    "winner_source": str((dual_gate.get("selector", {}) or {}).get("winner_source", "")),
                },
                "delta_oracle": float(gated_score - baseline_score),
            }
        )

    baseline_pass_rate = _pass_rate(baseline_passes)
    gated_pass_rate = _pass_rate(gated_passes)
    baseline_oracle = float(sum(baseline_scores) / max(1, len(baseline_scores)))
    gated_oracle = float(sum(gated_scores) / max(1, len(gated_scores)))
    trigger_rate = _pass_rate(gate_triggered)

    payload = {
        "suite": "pr4_dual_gate",
        "seed": seed,
        "num_cases": len(CASE_PROMPTS),
        "summary": {
            "baseline": {
                "pass_rate": baseline_pass_rate,
                "mean_oracle_score": baseline_oracle,
            },
            "dual_gated": {
                "pass_rate": gated_pass_rate,
                "mean_oracle_score": gated_oracle,
                "pass_rate_delta_vs_baseline": float(gated_pass_rate - baseline_pass_rate),
                "oracle_delta_vs_baseline": float(gated_oracle - baseline_oracle),
                "trigger_rate": trigger_rate,
            },
        },
        "cases": rows,
    }

    reports = Path("reports")
    reports.mkdir(parents=True, exist_ok=True)
    out_path = reports / "dual_gated_eval.json"
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
