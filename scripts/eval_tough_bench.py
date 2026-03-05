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


def _safe_int(value: Any, *, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic scoring over tough benchmark rows.")
    parser.add_argument("--dataset", default="datasets/tough_benchmarks.jsonl")
    parser.add_argument("--output", default="reports/tough_bench.json")
    parser.add_argument("--max-error-details", type=int, default=80)
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    dataset_path = _resolve_path(repo_root, str(args.dataset))
    output_path = _resolve_path(repo_root, str(args.output))

    cases, errors, skipped = load_cases(dataset_path, allowed_splits=ALLOWED_SPLITS)
    rows, summary = evaluate_cases(cases)

    counts = dict(summary["counts"])
    counts["invalid_rows"] = int(len(errors))
    counts["malformed_rows"] = int(sum(1 for row in errors if str(row.get("type")) == "malformed_json"))
    counts["skipped_non_target_splits"] = int(skipped)

    metrics = dict(summary["metrics"])
    pass_rate = float(metrics.get("pass_rate", 0.0))
    by_split = metrics.get("by_split") or {}
    adversarial_rate = float((by_split.get("adversarial", {}) or {}).get("pass_rate", 0.0))
    ood_rate = float((by_split.get("ood", {}) or {}).get("pass_rate", 0.0))
    worst_category = float(metrics.get("worst_category_pass_rate", 0.0))

    checks = {
        "overall_pass_rate_floor": bool(pass_rate >= 0.75),
        "adversarial_pass_rate_floor": bool(adversarial_rate >= 0.60),
        "ood_pass_rate_floor": bool(ood_rate >= 0.65),
        "worst_category_floor": bool(worst_category >= 0.60),
        "balanced_by_split": bool(((metrics.get("balance") or {}).get("balanced_by_split", False))),
        "balanced_by_category": bool(((metrics.get("balance") or {}).get("balanced_by_category", False))),
    }

    status = "pass" if _safe_int(counts.get("num_cases"), default=0) > 0 else "fail"

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
        "errors": errors[: max(0, int(args.max_error_details))],
        "cases": rows,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Wrote {output_path}")
    return 0 if status == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
