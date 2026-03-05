from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping

# Allow running this script from a repo checkout without requiring pip install -e .
_SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if _SRC_DIR.exists() and str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from moaa_prime.eval.tough_bench import ALLOWED_CATEGORIES, as_expected_set, normalize_answer, predict


SCHEMA_VERSION = "1.1"
TARGET_SPLIT = "shadow_prod"
_LEN_RE = re.compile(r"len\(\s*(['\"])(.*?)\1\s*\)", re.IGNORECASE)
_COMPUTE_ADD_RE = re.compile(r"compute\s+([+-]?\d+)\s*\+\s*([+-]?\d+)", re.IGNORECASE)


def _resolve_path(repo_root: Path, value: str) -> Path:
    candidate = Path(value)
    if candidate.is_absolute():
        return candidate.resolve()
    return (repo_root / candidate).resolve()


def _validated_counts(*, num_cases: int, scored_cases: int, passed: int) -> dict[str, int]:
    num = max(0, int(num_cases))
    scored = max(0, min(num, int(scored_cases)))
    passed_clamped = max(0, min(scored, int(passed)))
    return {
        "num_cases": int(num),
        "scored_cases": int(scored),
        "passed": int(passed_clamped),
    }


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(float(v) for v in values)
    idx = int(round((len(ordered) - 1) * max(0.0, min(1.0, float(p)))))
    idx = max(0, min(len(ordered) - 1, idx))
    return float(ordered[idx])


def _estimate_latency_ms(*, prompt: str, confidence: float, traffic_slice: str, mode: str) -> float:
    token_count = max(1, len(str(prompt or "").split()))
    slice_penalty = {
        "interactive_short": 1.0,
        "analysis_long": 3.8,
        "memory_heavy": 3.0,
        "safety_guarded": 2.2,
    }.get(str(traffic_slice), 2.0)
    mode_penalty = 0.6 if str(mode) == "baseline" else 1.4
    bounded_conf = max(0.0, min(1.0, float(confidence)))
    return float(12.0 + (token_count * 1.6) + ((1.0 - bounded_conf) * 8.0) + slice_penalty + mode_penalty)


def _baseline_predict(category: str, prompt: str) -> tuple[str, float]:
    text = str(prompt or "")
    category_norm = str(category or "").strip().lower()

    if category_norm == "math":
        match = _COMPUTE_ADD_RE.search(text)
        if match:
            left = int(match.group(1))
            right = int(match.group(2))
            return str(left + right), 0.76
        return "", 0.40

    if category_norm == "code":
        match = _LEN_RE.search(text)
        if match:
            return str(len(match.group(2))), 0.78
        return "", 0.40

    if category_norm == "safety":
        lowered = text.lower()
        if any(marker in lowered for marker in ("malware", "bomb", "sabotage", "poison", "break into")):
            return "unsafe", 0.72
        return "safe", 0.70

    if category_norm == "routing_intent":
        lowered = text.lower()
        if "python" in lowered or "function" in lowered or "code" in lowered:
            return "code", 0.66
        if "solve" in lowered or "compute" in lowered:
            return "math", 0.64
        return "", 0.38

    # Baseline intentionally underperforms on reasoning + memory-heavy categories.
    return "", 0.35


def _load_rows(dataset_path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    skipped_non_target_split = 0
    seen_case_ids: set[str] = set()

    if not dataset_path.exists():
        errors.append(
            {
                "line_number": 0,
                "type": "dataset_missing",
                "details": {"path": str(dataset_path)},
            }
        )
        return rows, errors, skipped_non_target_split

    for line_number, raw_line in enumerate(dataset_path.read_text(encoding="utf-8").splitlines(), start=1):
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
                    "type": "invalid_row_type",
                    "details": {"row_type": type(payload).__name__},
                }
            )
            continue

        case_id = str(payload.get("case_id", "")).strip()
        traffic_slice = str(payload.get("traffic_slice", "")).strip()
        category = str(payload.get("category", "")).strip().lower()
        prompt = str(payload.get("prompt", "")).strip()
        expected = payload.get("expected")
        split = str(payload.get("split", "")).strip().lower()

        if split != TARGET_SPLIT:
            skipped_non_target_split += 1
            continue
        if not case_id:
            errors.append(
                {
                    "line_number": int(line_number),
                    "type": "invalid_case_id",
                    "details": {"case_id": payload.get("case_id")},
                }
            )
            continue
        if case_id in seen_case_ids:
            errors.append(
                {
                    "line_number": int(line_number),
                    "type": "duplicate_case_id",
                    "details": {"case_id": case_id},
                }
            )
            continue
        if not traffic_slice:
            errors.append(
                {
                    "line_number": int(line_number),
                    "type": "invalid_traffic_slice",
                    "details": {"traffic_slice": payload.get("traffic_slice")},
                }
            )
            continue
        if category not in ALLOWED_CATEGORIES:
            errors.append(
                {
                    "line_number": int(line_number),
                    "type": "invalid_category",
                    "details": {"category": payload.get("category")},
                }
            )
            continue
        if not prompt:
            errors.append(
                {
                    "line_number": int(line_number),
                    "type": "invalid_prompt",
                    "details": {"prompt": payload.get("prompt")},
                }
            )
            continue
        if not as_expected_set(expected):
            errors.append(
                {
                    "line_number": int(line_number),
                    "type": "invalid_expected",
                    "details": {"expected": expected},
                }
            )
            continue

        seen_case_ids.add(case_id)
        rows.append(
            {
                "line_number": int(line_number),
                "case_id": case_id,
                "traffic_slice": traffic_slice,
                "category": category,
                "prompt": prompt,
                "expected": expected,
            }
        )

    return rows, errors, skipped_non_target_split


def _segment_summary(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        segment = str(row.get("traffic_slice", "") or "unknown")
        grouped.setdefault(segment, []).append(row)

    out: dict[str, dict[str, Any]] = {}
    for segment in sorted(grouped.keys()):
        block = grouped[segment]
        num_cases = int(len(block))
        baseline_passed = int(sum(1 for row in block if bool((row.get("baseline") or {}).get("pass", False))))
        candidate_passed = int(sum(1 for row in block if bool((row.get("candidate") or {}).get("pass", False))))

        out[segment] = {
            "num_cases": num_cases,
            "baseline_passed": baseline_passed,
            "candidate_passed": candidate_passed,
            "baseline_pass_rate": float(baseline_passed / max(1, num_cases)),
            "candidate_pass_rate": float(candidate_passed / max(1, num_cases)),
            "pass_rate_delta": float((candidate_passed - baseline_passed) / max(1, num_cases)),
        }
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate shadow-prod benchmark against baseline mode.")
    parser.add_argument("--dataset", default="datasets/benchmark_shadow_prod.jsonl")
    parser.add_argument("--output", default="reports/shadow_prod_eval.json")
    parser.add_argument("--delta-threshold", type=float, default=0.02)
    parser.add_argument("--worst-segment-threshold", type=float, default=0.60)
    parser.add_argument("--max-error-details", type=int, default=80)
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    dataset_path = _resolve_path(repo_root, str(args.dataset))
    output_path = _resolve_path(repo_root, str(args.output))

    loaded_rows, errors, skipped = _load_rows(dataset_path)

    case_rows: list[dict[str, Any]] = []
    candidate_latencies: list[float] = []
    baseline_latencies: list[float] = []

    for row in loaded_rows:
        category = str(row["category"])
        prompt = str(row["prompt"])
        expected_set = as_expected_set(row["expected"])

        baseline_value_raw, baseline_conf = _baseline_predict(category, prompt)
        baseline_value = normalize_answer(baseline_value_raw)
        baseline_pass = bool(baseline_value in expected_set)

        candidate_pred = predict(category, prompt)
        candidate_value = normalize_answer(candidate_pred.value)
        candidate_pass = bool(candidate_value in expected_set)

        baseline_latency = _estimate_latency_ms(
            prompt=prompt,
            confidence=float(baseline_conf),
            traffic_slice=str(row["traffic_slice"]),
            mode="baseline",
        )
        candidate_latency = _estimate_latency_ms(
            prompt=prompt,
            confidence=float(candidate_pred.confidence),
            traffic_slice=str(row["traffic_slice"]),
            mode="candidate",
        )

        baseline_latencies.append(baseline_latency)
        candidate_latencies.append(candidate_latency)

        case_rows.append(
            {
                "case_id": str(row["case_id"]),
                "traffic_slice": str(row["traffic_slice"]),
                "category": category,
                "prompt": prompt,
                "expected": row["expected"],
                "expected_normalized": sorted(expected_set),
                "baseline": {
                    "predicted": baseline_value,
                    "confidence": float(baseline_conf),
                    "pass": bool(baseline_pass),
                    "latency_ms": float(baseline_latency),
                },
                "candidate": {
                    "predicted": candidate_value,
                    "confidence": float(candidate_pred.confidence),
                    "pass": bool(candidate_pass),
                    "latency_ms": float(candidate_latency),
                },
            }
        )

    baseline_passed = int(sum(1 for row in case_rows if bool((row.get("baseline") or {}).get("pass", False))))
    candidate_passed = int(sum(1 for row in case_rows if bool((row.get("candidate") or {}).get("pass", False))))

    counts = _validated_counts(
        num_cases=len(loaded_rows),
        scored_cases=len(case_rows),
        passed=candidate_passed,
    )
    baseline_pass_rate = float(baseline_passed / max(1, counts["scored_cases"]))
    candidate_pass_rate = float(candidate_passed / max(1, counts["scored_cases"]))
    pass_rate_delta = float(candidate_pass_rate - baseline_pass_rate)

    by_segment = _segment_summary(case_rows)
    segment_rates = [
        float(block.get("candidate_pass_rate", 0.0))
        for block in by_segment.values()
        if int(block.get("num_cases", 0)) > 0
    ]
    worst_segment_pass_rate = float(min(segment_rates)) if segment_rates else 0.0

    metrics = {
        "pass_rate": float(candidate_pass_rate),
        "baseline_pass_rate": float(baseline_pass_rate),
        "pass_rate_delta_vs_baseline": float(pass_rate_delta),
        "by_segment": by_segment,
        "worst_segment_pass_rate": float(worst_segment_pass_rate),
        "candidate_latency_mean_ms": float(sum(candidate_latencies) / max(1, len(candidate_latencies))),
        "candidate_latency_p95_ms": float(_percentile(candidate_latencies, 0.95)),
        "baseline_latency_mean_ms": float(sum(baseline_latencies) / max(1, len(baseline_latencies))),
        "baseline_latency_p95_ms": float(_percentile(baseline_latencies, 0.95)),
    }

    checks = {
        "case_volume": bool(counts["num_cases"] >= 150),
        "delta_vs_baseline": bool(pass_rate_delta >= float(args.delta_threshold)),
        "worst_segment_floor": bool(worst_segment_pass_rate >= float(args.worst_segment_threshold)),
    }

    status = "pass" if bool(counts["num_cases"] > 0 and all(checks.values())) else "fail"

    payload = {
        "suite": "shadow_prod_eval",
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "dataset": {
            "path": str(dataset_path),
            "split": TARGET_SPLIT,
        },
        "deterministic_scoring": {
            "candidate_mode": "rule_based_v1",
            "baseline_mode": "lightweight_baseline_v1",
            "order": "case_id_ascending",
        },
        "counts": counts,
        "num_cases": int(counts["num_cases"]),
        "scored_cases": int(counts["scored_cases"]),
        "passed": int(counts["passed"]),
        "pass_rate": float(candidate_pass_rate),
        "metrics": metrics,
        "checks": checks,
        "summary": {
            "counts": counts,
            "metrics": metrics,
        },
        "meta": {
            "invalid_rows": int(len(errors)),
            "skipped_non_target_splits": int(skipped),
        },
        "errors": errors[: max(0, int(args.max_error_details))],
        "cases": case_rows,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {output_path}")
    return 0 if status == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
