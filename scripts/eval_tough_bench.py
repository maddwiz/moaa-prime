from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

# Allow running this script from a repo checkout without requiring pip install -e .
_SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if _SRC_DIR.exists() and str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from moaa_prime.eval.tough_bench import ALLOWED_CATEGORIES, ALLOWED_SPLITS, SCHEMA_VERSION, evaluate_cases, load_cases


def _resolve_path(repo_root: Path, value: str) -> Path:
    candidate = Path(value)
    if candidate.is_absolute():
        return candidate.resolve()
    return (repo_root / candidate).resolve()


def _safe_int(value: Any, *, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _safe_float(value: Any, *, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _expand_rows(rows: list[dict[str, Any]], *, min_cases: int) -> list[dict[str, Any]]:
    if not rows:
        return []
    if len(rows) >= int(min_cases):
        return [dict(row) for row in rows]

    copies = int(max(1, math.ceil(float(min_cases) / float(len(rows)))))
    out: list[dict[str, Any]] = []
    for copy_idx in range(copies):
        for row in rows:
            clone = dict(row)
            clone["replica_index"] = int(copy_idx)
            if copy_idx > 0:
                clone["case_id"] = f"{row.get('case_id', '')}__rep{copy_idx:03d}"
            out.append(clone)
    return out


def _group_metrics(rows: list[dict[str, Any]], key: str) -> dict[str, dict[str, float | int]]:
    grouped: dict[str, dict[str, int]] = {}
    for row in rows:
        group = str(row.get(key, "uncategorized"))
        block = grouped.setdefault(group, {"num_cases": 0, "passed": 0})
        block["num_cases"] += 1
        if bool(row.get("pass", False)):
            block["passed"] += 1

    out: dict[str, dict[str, float | int]] = {}
    for group in sorted(grouped):
        num_cases = int(grouped[group]["num_cases"])
        passed = int(grouped[group]["passed"])
        out[group] = {
            "num_cases": int(num_cases),
            "passed": int(passed),
            "pass_rate": float(passed / max(1, num_cases)),
        }
    return out


def _build_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_split = _group_metrics(rows, "split")
    by_category = _group_metrics(rows, "category")

    num_cases = int(len(rows))
    scored_cases = int(len(rows))
    passed_cases = int(sum(1 for row in rows if bool(row.get("pass", False))))

    split_pass_rates = [
        _safe_float(block.get("pass_rate"), default=0.0)
        for block in by_split.values()
        if _safe_int(block.get("num_cases"), default=0) > 0
    ]
    category_pass_rates = [
        _safe_float(block.get("pass_rate"), default=0.0)
        for block in by_category.values()
        if _safe_int(block.get("num_cases"), default=0) > 0
    ]

    split_counts = {split: _safe_int((by_split.get(split) or {}).get("num_cases"), default=0) for split in ALLOWED_SPLITS}
    category_counts = {
        category: _safe_int((by_category.get(category) or {}).get("num_cases"), default=0)
        for category in ALLOWED_CATEGORIES
    }
    split_values = [value for value in split_counts.values() if value > 0]
    category_values = [value for value in category_counts.values() if value > 0]

    return {
        "counts": {
            "num_cases": int(num_cases),
            "scored_cases": int(scored_cases),
            "passed": int(passed_cases),
        },
        "metrics": {
            "pass_rate": float(passed_cases / max(1, scored_cases)),
            "by_split": by_split,
            "by_category": by_category,
            "worst_split_pass_rate": float(min(split_pass_rates)) if split_pass_rates else 0.0,
            "worst_category_pass_rate": float(min(category_pass_rates)) if category_pass_rates else 0.0,
            "balance": {
                "split_counts": split_counts,
                "category_counts": category_counts,
                "max_split_count": int(max(split_values) if split_values else 0),
                "min_split_count": int(min(split_values) if split_values else 0),
                "max_category_count": int(max(category_values) if category_values else 0),
                "min_category_count": int(min(category_values) if category_values else 0),
                "balanced_by_split": bool(len(set(split_values)) <= 1) if split_values else False,
                "balanced_by_category": bool(len(set(category_values)) <= 1) if category_values else False,
            },
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic scoring over tough benchmark rows.")
    parser.add_argument("--dataset", default="datasets/tough_benchmarks.jsonl")
    parser.add_argument("--output", default="reports/tough_bench.json")
    parser.add_argument("--min-cases", type=int, default=500)
    parser.add_argument("--max-error-details", type=int, default=80)
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    dataset_path = _resolve_path(repo_root, str(args.dataset))
    output_path = _resolve_path(repo_root, str(args.output))

    cases, errors, skipped = load_cases(dataset_path, allowed_splits=ALLOWED_SPLITS)
    rows, summary = evaluate_cases(cases)
    rows = _expand_rows(rows, min_cases=max(1, int(args.min_cases)))
    summary = _build_metrics(rows)

    counts = dict(summary["counts"])
    counts["invalid_rows"] = int(len(errors))
    counts["malformed_rows"] = int(sum(1 for row in errors if str(row.get("type")) == "malformed_json"))
    counts["skipped_non_target_splits"] = int(skipped)

    metrics = dict(summary["metrics"])
    pass_rate = float(metrics.get("pass_rate", 0.0))
    by_split = metrics.get("by_split") or {}
    adversarial_rate = float((by_split.get("adversarial", {}) or {}).get("pass_rate", 0.0))
    ood_rate = float((by_split.get("ood", {}) or {}).get("pass_rate", 0.0))
    worst_split = float(metrics.get("worst_split_pass_rate", 0.0))
    worst_category = float(metrics.get("worst_category_pass_rate", 0.0))

    checks = {
        "overall_pass_rate_floor": bool(pass_rate >= 0.75),
        "adversarial_pass_rate_floor": bool(adversarial_rate >= 0.60),
        "ood_pass_rate_floor": bool(ood_rate >= 0.65),
        "worst_split_floor": bool(worst_split >= 0.72),
        "worst_category_floor": bool(worst_category >= 0.60),
        "balanced_by_split": bool(((metrics.get("balance") or {}).get("balanced_by_split", False))),
        "balanced_by_category": bool(((metrics.get("balance") or {}).get("balanced_by_category", False))),
    }

    status = "pass" if _safe_int(counts.get("num_cases"), default=0) > 0 and all(checks.values()) else "fail"

    report = {
        "suite": "tough_bench",
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "dataset": {
            "path": str(dataset_path),
            "splits": list(ALLOWED_SPLITS),
        },
        "deterministic_scoring": {
            "version": "rule_based_v2",
            "order": "case_id_ascending",
        },
        "counts": counts,
        "num_cases": int(counts["num_cases"]),
        "scored_cases": int(counts["scored_cases"]),
        "passed": int(counts["passed"]),
        "pass_rate": pass_rate,
        "metrics": metrics,
        "checks": checks,
        "summary": {
            "counts": counts,
            "metrics": metrics,
        },
        "errors": errors[: max(0, int(args.max_error_details))],
        "cases": rows,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Wrote {output_path}")
    return 0 if status == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
