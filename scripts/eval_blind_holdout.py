from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping

# Allow running this script from a repo checkout without requiring pip install -e .
_SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if _SRC_DIR.exists() and str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from moaa_prime.eval.tough_bench import as_expected_set, normalize_answer, predict


SCHEMA_VERSION = "1.1"
SUITE = "blind_holdout"
TARGET_SPLIT = "holdout_locked"
PASS_RATE_FLOOR = 0.72
WORST_CATEGORY_FLOOR = 0.60
LATENCY_P95_BUDGET_MS = 280.0


def _resolve_path(repo_root: Path, value: str) -> Path:
    candidate = Path(value)
    if candidate.is_absolute():
        return candidate.resolve()
    return (repo_root / candidate).resolve()


def _safe_float(value: Any, *, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _latency_proxy_ms(*, prompt: str, category: str, confidence: float) -> float:
    token_count = max(1, len(str(prompt or "").split()))
    category_bias = {
        "math": 4.5,
        "code": 6.0,
        "reasoning": 9.0,
        "safety": 4.0,
        "routing_intent": 7.0,
        "memory_behavior": 8.5,
    }.get(str(category or "").strip().lower(), 6.0)
    confidence_bonus = max(0.0, min(1.0, float(confidence))) * 5.0
    return float(32.0 + (1.7 * token_count) + category_bias - confidence_bonus)


def _p95(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(float(v) for v in values)
    idx = int(round((len(ordered) - 1) * 0.95))
    idx = max(0, min(len(ordered) - 1, idx))
    return float(ordered[idx])


def _validated_counts(*, num_cases: int, scored_cases: int, passed: int) -> dict[str, int]:
    num = max(0, int(num_cases))
    scored = max(0, min(num, int(scored_cases)))
    passed_clamped = max(0, min(scored, int(passed)))
    return {
        "num_cases": int(num),
        "scored_cases": int(scored),
        "passed": int(passed_clamped),
    }


def _load_rows(path: Path, *, split: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    skipped = 0

    if not path.exists():
        return [], [{"line_number": 0, "type": "dataset_missing", "details": {"path": str(path)}}], 0

    required_fields = {"case_id", "category", "prompt", "expected", "split", "source"}

    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(
                {
                    "line_number": int(line_number),
                    "type": "malformed_json",
                    "details": {"message": str(exc)},
                }
            )
            continue

        if not isinstance(payload, Mapping):
            errors.append(
                {
                    "line_number": int(line_number),
                    "type": "invalid_row",
                    "details": {"reason": "row must be an object"},
                }
            )
            continue

        missing = sorted(required_fields - set(payload.keys()))
        if missing:
            errors.append(
                {
                    "line_number": int(line_number),
                    "type": "missing_required_fields",
                    "details": {"missing": missing},
                }
            )
            continue

        row_split = str(payload.get("split", "") or "").strip().lower()
        if row_split != str(split).strip().lower():
            skipped += 1
            continue

        case_id = str(payload.get("case_id", "") or "").strip()
        category = str(payload.get("category", "") or "").strip()
        prompt = str(payload.get("prompt", "") or "").strip()
        expected_values = as_expected_set(payload.get("expected"))
        source = payload.get("source")
        if not case_id or not category or not prompt or not expected_values or not isinstance(source, Mapping):
            errors.append(
                {
                    "line_number": int(line_number),
                    "type": "invalid_case",
                    "details": {"case_id": case_id, "category": category},
                }
            )
            continue

        rows.append(
            {
                "line_number": int(line_number),
                "case_id": case_id,
                "category": category,
                "prompt": prompt,
                "expected_raw": payload.get("expected"),
                "expected_set": sorted(expected_values),
                "source": dict(source),
            }
        )

    return rows, errors, skipped


def _evaluate_rows(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    results: list[dict[str, Any]] = []
    by_category: dict[str, dict[str, Any]] = {}
    latencies: list[float] = []

    for row in rows:
        category = str(row["category"])
        prediction = predict(category, str(row["prompt"]))
        predicted = normalize_answer(prediction.value)
        expected_set = set(row["expected_set"])
        passed = bool(predicted in expected_set)
        latency_ms = _latency_proxy_ms(
            prompt=str(row["prompt"]),
            category=category,
            confidence=_safe_float(prediction.confidence),
        )
        latencies.append(latency_ms)

        block = by_category.setdefault(category, {"num_cases": 0, "passed": 0})
        block["num_cases"] = int(block["num_cases"]) + 1
        block["passed"] = int(block["passed"]) + (1 if passed else 0)

        results.append(
            {
                "case_id": str(row["case_id"]),
                "category": category,
                "prompt": str(row["prompt"]),
                "expected": row["expected_raw"],
                "prediction": predicted,
                "confidence": float(_safe_float(prediction.confidence)),
                "pass": bool(passed),
                "latency_proxy_ms": float(latency_ms),
            }
        )

    for category, block in by_category.items():
        num_cases = int(block["num_cases"])
        passed = int(block["passed"])
        block["scored_cases"] = int(num_cases)
        block["pass_rate"] = float(passed / max(1, num_cases))

    num_cases = int(len(results))
    passed = int(sum(1 for row in results if bool(row["pass"])))
    counts = _validated_counts(num_cases=num_cases, scored_cases=num_cases, passed=passed)
    pass_rate = float(counts["passed"] / max(1, counts["scored_cases"]))
    worst_category = float(min((block["pass_rate"] for block in by_category.values()), default=0.0))

    return results, {
        "counts": counts,
        "metrics": {
            "pass_rate": float(pass_rate),
            "latency_p95_ms": float(_p95(latencies)),
            "worst_category_pass_rate": float(worst_category),
            "by_category": by_category,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate the locked blind holdout benchmark with deterministic scoring.")
    parser.add_argument("--dataset", default="datasets/benchmark_holdout_locked.jsonl")
    parser.add_argument("--output", default="reports/blind_holdout.json")
    parser.add_argument("--pass-rate-floor", type=float, default=PASS_RATE_FLOOR)
    parser.add_argument("--worst-category-floor", type=float, default=WORST_CATEGORY_FLOOR)
    parser.add_argument("--latency-p95-budget-ms", type=float, default=LATENCY_P95_BUDGET_MS)
    parser.add_argument("--max-error-details", type=int, default=80)
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    dataset_path = _resolve_path(repo_root, str(args.dataset))
    output_path = _resolve_path(repo_root, str(args.output))

    rows, errors, skipped = _load_rows(dataset_path, split=TARGET_SPLIT)
    case_rows, summary = _evaluate_rows(rows)

    metrics = dict(summary["metrics"])
    counts = dict(summary["counts"])
    checks = {
        "pass_rate_floor": bool(float(metrics["pass_rate"]) >= float(args.pass_rate_floor)),
        "worst_category_floor": bool(float(metrics["worst_category_pass_rate"]) >= float(args.worst_category_floor)),
        "latency_p95_budget": bool(float(metrics["latency_p95_ms"]) <= float(args.latency_p95_budget_ms)),
    }
    status = "pass" if int(counts["num_cases"]) > 0 and all(checks.values()) else "fail"

    report = {
        "suite": SUITE,
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "dataset": {
            "path": str(dataset_path),
            "target_split": TARGET_SPLIT,
        },
        "counts": counts,
        "num_cases": int(counts["num_cases"]),
        "scored_cases": int(counts["scored_cases"]),
        "passed": int(counts["passed"]),
        "pass_rate": float(metrics["pass_rate"]),
        "metrics": metrics,
        "summary": {
            "counts": counts,
            "metrics": metrics,
            "checks": checks,
        },
        "checks": checks,
        "meta": {
            "invalid_rows": int(len(errors)),
            "skipped_non_target_splits": int(skipped),
        },
        "errors": errors[: max(0, int(args.max_error_details))],
        "cases": case_rows,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Wrote {output_path}")
    return 0 if status == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
