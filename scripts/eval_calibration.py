from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# Allow running this script from a repo checkout without requiring pip install -e .
_SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if _SRC_DIR.exists() and str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from moaa_prime.eval.tough_bench import ALLOWED_SPLITS, SCHEMA_VERSION, evaluate_cases, load_cases


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


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(float(lo), min(float(hi), float(value)))


def _build_bins(rows: list[dict[str, Any]], bin_count: int) -> list[dict[str, Any]]:
    size = max(1, int(bin_count))
    bucket_rows: list[list[dict[str, Any]]] = [[] for _ in range(size)]

    for row in rows:
        confidence = _clamp(_safe_float(row.get("confidence"), default=0.0))
        idx = min(size - 1, int(confidence * size))
        bucket_rows[idx].append(row)

    bins: list[dict[str, Any]] = []
    for idx, bucket in enumerate(bucket_rows):
        lower = idx / size
        upper = (idx + 1) / size
        if bucket:
            avg_confidence = sum(_safe_float(row.get("confidence"), default=0.0) for row in bucket) / len(bucket)
            accuracy = sum(1.0 for row in bucket if bool(row.get("pass", False))) / len(bucket)
        else:
            avg_confidence = 0.0
            accuracy = 0.0

        bins.append(
            {
                "bin": int(idx),
                "range": [float(lower), float(upper)],
                "count": int(len(bucket)),
                "avg_confidence": float(avg_confidence),
                "accuracy": float(accuracy),
                "gap": float(abs(avg_confidence - accuracy)),
            }
        )
    return bins


def _expected_calibration_error(bins: list[dict[str, Any]], total_cases: int) -> float:
    if total_cases <= 0:
        return 0.0
    weighted_gap = 0.0
    for block in bins:
        count = int(block.get("count", 0))
        gap = _safe_float(block.get("gap"), default=0.0)
        weighted_gap += (count / total_cases) * gap
    return float(weighted_gap)


def _brier_score(rows: list[dict[str, Any]]) -> float:
    if not rows:
        return 0.0
    total = 0.0
    for row in rows:
        y = 1.0 if bool(row.get("pass", False)) else 0.0
        p = _clamp(_safe_float(row.get("confidence"), default=0.0))
        total += (p - y) ** 2
    return float(total / len(rows))


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate confidence calibration on tough benchmark predictions.")
    parser.add_argument("--dataset", default="datasets/tough_benchmarks.jsonl")
    parser.add_argument("--output", default="reports/calibration.json")
    parser.add_argument("--bins", type=int, default=10)
    parser.add_argument("--ece-max", type=float, default=0.12)
    parser.add_argument("--brier-max", type=float, default=0.25)
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    dataset_path = _resolve_path(repo_root, str(args.dataset))
    output_path = _resolve_path(repo_root, str(args.output))

    cases, errors, skipped = load_cases(dataset_path, allowed_splits=ALLOWED_SPLITS)
    rows, summary = evaluate_cases(cases)

    counts = dict(summary["counts"])
    bins = _build_bins(rows, bin_count=int(args.bins))
    ece = _expected_calibration_error(bins, total_cases=int(counts["num_cases"]))
    brier = _brier_score(rows)
    mean_confidence = sum(_safe_float(row.get("confidence"), default=0.0) for row in rows) / max(1, len(rows))

    metrics = {
        "ece": float(ece),
        "brier_score": float(brier),
        "mean_confidence": float(mean_confidence),
        "pass_rate": float(summary["metrics"]["pass_rate"]),
        "by_split": dict(summary["metrics"]["by_split"]),
    }
    checks = {
        "ece_within_budget": bool(ece <= float(args.ece_max)),
        "brier_within_budget": bool(brier <= float(args.brier_max)),
    }

    status = "pass" if int(counts["num_cases"]) > 0 and all(checks.values()) else "fail"

    report = {
        "suite": "prod_calibration",
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "dataset": {
            "path": str(dataset_path),
            "splits": list(ALLOWED_SPLITS),
        },
        "config": {
            "bins": int(args.bins),
            "ece_max": float(args.ece_max),
            "brier_max": float(args.brier_max),
        },
        "counts": counts,
        "num_cases": int(counts["num_cases"]),
        "scored_cases": int(counts["scored_cases"]),
        "passed": int(counts["passed"]),
        "pass_rate": float(summary["metrics"]["pass_rate"]),
        "metrics": metrics,
        "checks": checks,
        "summary": {
            "counts": counts,
            "metrics": metrics,
            "checks": checks,
        },
        "bins": bins,
        "skipped_non_target_splits": int(skipped),
        "invalid_rows": int(len(errors)),
        "cases": [
            {
                "case_id": row["case_id"],
                "split": row["split"],
                "category": row["category"],
                "correct": bool(row["pass"]),
                "confidence": float(_clamp(_safe_float(row.get("confidence"), default=0.0))),
            }
            for row in rows
        ],
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Wrote {output_path}")
    return 0 if status == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
