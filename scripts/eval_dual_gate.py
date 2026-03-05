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
from moaa_prime.eval.cases import CATEGORY_ORDER, CORE_EVAL_CASES


PASS_THRESHOLD = 0.70
DEFAULT_MIN_CASES = 150
DUAL_GATE_CONFIG: dict[str, float] = {
    "low_confidence_threshold": 0.60,
    "high_ambiguity_threshold": 0.85,
}


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


def _expand_cases_category_balanced(
    cases: list[dict[str, object]],
    *,
    min_total: int,
) -> list[dict[str, object]]:
    original = [dict(case) for case in cases]
    if not original:
        return []
    if int(min_total) <= len(original):
        return original

    grouped: dict[str, list[dict[str, object]]] = {}
    for case in original:
        category = str(case.get("category", "") or "uncategorized")
        grouped.setdefault(category, []).append(case)

    ordered_categories: list[str] = []
    seen: set[str] = set()
    for category in CATEGORY_ORDER:
        if category in grouped and grouped[category]:
            ordered_categories.append(category)
            seen.add(category)
    for category in sorted(grouped.keys()):
        if category in seen:
            continue
        ordered_categories.append(category)

    if not ordered_categories:
        return original

    per_category_target = (int(min_total) + len(ordered_categories) - 1) // len(ordered_categories)
    expanded_by_category: dict[str, list[dict[str, object]]] = {}
    for category in ordered_categories:
        source = grouped.get(category, [])
        if not source:
            continue
        source_count = len(source)
        out: list[dict[str, object]] = []
        for idx in range(per_category_target):
            base = source[idx % source_count]
            row = dict(base)
            base_id = str(base.get("id", "") or "case")
            if idx >= source_count:
                row["id"] = f"{base_id}__rep{idx:03d}"
            out.append(row)
        expanded_by_category[category] = out

    expanded: list[dict[str, object]] = []
    for idx in range(per_category_target):
        for category in ordered_categories:
            rows = expanded_by_category.get(category, [])
            if idx < len(rows):
                expanded.append(rows[idx])
    return expanded


def _expanded_eval_cases(*, min_cases: int) -> list[dict[str, object]]:
    return _expand_cases_category_balanced(CORE_EVAL_CASES, min_total=int(min_cases))


def _setup_prompt(case: dict[str, object]) -> str:
    return str(case.get("setup_prompt", "") or "").strip()


def _prime_case_memory(app: MoAAPrime, *, setup_prompt: str, task_id: str) -> None:
    if not setup_prompt:
        return
    app.run_once(
        setup_prompt,
        task_id=f"{task_id}-setup",
        mode="v3",
        budget={"mode": "balanced"},
        memory_hints={"default": 0.8, "math-agent": 0.75, "code-agent": 0.75},
    )


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


def _validated_counts(*, num_cases: int, scored_cases: int, passed: int) -> dict[str, int]:
    num = max(0, int(num_cases))
    scored = max(0, min(num, int(scored_cases)))
    passed_clamped = max(0, min(scored, int(passed)))
    return {
        "num_cases": int(num),
        "scored_cases": int(scored),
        "passed": int(passed_clamped),
    }


def _run_counts(*, scores: list[float], passes: list[bool]) -> dict[str, int]:
    return _validated_counts(
        num_cases=int(len(scores)),
        scored_cases=int(len(scores)),
        passed=int(sum(1 for value in passes if value)),
    )


def _run_summary(*, config_id: str, scores: list[float], passes: list[bool]) -> dict[str, object]:
    counts = _run_counts(scores=scores, passes=passes)
    pass_rate = _pass_rate(passes)
    mean_oracle_score = float(sum(scores) / max(1, len(scores)))
    return {
        "config_id": config_id,
        "counts": counts,
        "num_cases": int(counts["num_cases"]),
        "scored_cases": int(counts["scored_cases"]),
        "passed": int(counts["passed"]),
        "pass_rate": pass_rate,
        "mean_oracle_score": mean_oracle_score,
        "metrics": {
            "pass_rate": pass_rate,
            "mean_oracle_score": mean_oracle_score,
        },
    }


def main() -> int:
    seed = int(os.getenv("MOAA_PR4_EVAL_SEED") or "29")
    pass_threshold = float(os.getenv("MOAA_PR4_PASS_THRESHOLD") or str(PASS_THRESHOLD))
    min_cases = _env_min_cases(
        "MOAA_PR4_DUAL_EVAL_MIN_CASES",
        default=DEFAULT_MIN_CASES,
        minimum=len(CORE_EVAL_CASES),
    )
    eval_cases = _expanded_eval_cases(min_cases=min_cases)

    rows = []
    baseline_scores: list[float] = []
    gated_scores: list[float] = []
    baseline_passes: list[bool] = []
    gated_passes: list[bool] = []
    gate_triggered: list[bool] = []

    for idx, case in enumerate(eval_cases):
        category = str(case.get("category", "") or "uncategorized")
        baseline_app = MoAAPrime(mode="v3", seed=seed)
        gated_app = MoAAPrime(mode="v3", seed=seed)
        setup_prompt = _setup_prompt(case)
        if setup_prompt:
            _prime_case_memory(baseline_app, setup_prompt=setup_prompt, task_id=f"pr4-baseline-{idx}")
            _prime_case_memory(gated_app, setup_prompt=setup_prompt, task_id=f"pr4-gated-{idx}")

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
            dual_gate_config=DUAL_GATE_CONFIG,
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
                "category": category,
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
    trigger_count = int(sum(1 for value in gate_triggered if value))

    baseline_summary = _run_summary(config_id="baseline", scores=baseline_scores, passes=baseline_passes)
    dual_summary = _run_summary(config_id="dual_gated", scores=gated_scores, passes=gated_passes)
    dual_summary["trigger_rate"] = float(trigger_rate)
    dual_summary["triggered"] = int(trigger_count)
    dual_summary["pass_rate_delta_vs_baseline"] = float(gated_pass_rate - baseline_pass_rate)
    dual_summary["oracle_delta_vs_baseline"] = float(gated_oracle - baseline_oracle)

    baseline_metrics = baseline_summary.get("metrics")
    if isinstance(baseline_metrics, dict):
        baseline_metrics["pass_threshold"] = float(pass_threshold)
    dual_metrics = dual_summary.get("metrics")
    if isinstance(dual_metrics, dict):
        dual_metrics["pass_rate_delta_vs_baseline"] = float(gated_pass_rate - baseline_pass_rate)
        dual_metrics["oracle_delta_vs_baseline"] = float(gated_oracle - baseline_oracle)
        dual_metrics["trigger_rate"] = float(trigger_rate)
        dual_metrics["triggered"] = int(trigger_count)

    counts = _validated_counts(
        num_cases=int(len(eval_cases)),
        scored_cases=int(len(eval_cases)),
        passed=int(dual_summary["passed"]),
    )

    payload = {
        "suite": "pr4_dual_gate",
        "schema_version": "1.1",
        "seed": seed,
        "pass_threshold": float(pass_threshold),
        "dual_gate_config": dict(DUAL_GATE_CONFIG),
        "counts": counts,
        "num_cases": int(counts["num_cases"]),
        "scored_cases": int(counts["scored_cases"]),
        "passed": int(counts["passed"]),
        "pass_rate": float(counts["passed"] / max(1, counts["scored_cases"])),
        "summary": {
            "baseline": baseline_summary,
            "dual_gated": dual_summary,
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
