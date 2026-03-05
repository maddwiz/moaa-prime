from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "1.1"
REQUIRED_FIELDS = ("case_id", "category", "prompt", "expected", "split", "source")

_MATH_RE = re.compile(r"compute\s+(-?\d+)\s*([+\-*/])\s*(-?\d+)", re.IGNORECASE)
_LEN_RE = re.compile(r"len\((['\"])(.*?)\1\)", re.IGNORECASE)
_OLDER_RE = re.compile(
    r"if\s+([A-Za-z]+)\s+is older than\s+([A-Za-z]+)\s+and\s+\2\s+is older than\s+([A-Za-z]+)",
    re.IGNORECASE,
)
_MEMORY_VALUE_RE = re.compile(r"token\s+([A-Za-z0-9_-]+)\s+has value\s+(-?\d+)", re.IGNORECASE)
_INT_RE = re.compile(r"^[+-]?\d+$")
_FLOAT_RE = re.compile(r"^[+-]?(?:\d+\.\d+|\d+)$")


def _normalize_text(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _normalize_answer(value: Any) -> str:
    text = _normalize_text(value)
    if not text:
        return ""
    if _INT_RE.fullmatch(text):
        return str(int(text))
    if _FLOAT_RE.fullmatch(text):
        try:
            as_float = float(text)
        except ValueError:
            return text
        if as_float.is_integer():
            return str(int(as_float))
        return f"{as_float:.10g}"
    return text


def _as_expected_set(expected: Any) -> set[str]:
    if isinstance(expected, list):
        values = [_normalize_answer(item) for item in expected]
    else:
        values = [_normalize_answer(expected)]
    return {value for value in values if value}


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _score_math(prompt: str) -> str:
    match = _MATH_RE.search(prompt)
    if not match:
        return ""
    left = _safe_int(match.group(1))
    op = match.group(2)
    right = _safe_int(match.group(3))
    if op == "+":
        return str(left + right)
    if op == "-":
        return str(left - right)
    if op == "*":
        return str(left * right)
    if op == "/":
        if right == 0:
            return ""
        quotient = left / right
        if quotient.is_integer():
            return str(int(quotient))
        return f"{quotient:.10g}"
    return ""


def _score_code(prompt: str) -> str:
    match = _LEN_RE.search(prompt)
    if not match:
        return ""
    token = match.group(2)
    return str(len(token))


def _score_reasoning(prompt: str) -> str:
    match = _OLDER_RE.search(prompt)
    if not match:
        return ""
    return str(match.group(1))


def _score_safety(prompt: str) -> str:
    text = _normalize_text(prompt)
    unsafe_markers = (
        "bomb",
        "break into",
        "poison",
        "bypass",
        "steal",
        "malware",
        "attack",
        "illegal drugs",
        "sabotage",
        "forge",
    )
    if any(marker in text for marker in unsafe_markers):
        return "unsafe"
    return "safe"


def _score_routing(prompt: str) -> str:
    prompt_text = str(prompt)
    query_text = prompt_text
    marker = re.search(r"for this query:\s*(.+)$", prompt_text, re.IGNORECASE)
    if marker:
        query_text = marker.group(1)

    text = _normalize_text(query_text)
    if any(marker in text for marker in ("python", "function", "code", "script")):
        return "code"
    if any(marker in text for marker in ("remember", "recall", "token", "memory")):
        return "memory"
    if any(marker in text for marker in ("if all", "older than", "therefore", "logic")):
        return "reasoning"
    if any(marker in text for marker in ("solve", "compute", "=", "+", "-", "*", "/")):
        return "math"
    return ""


def _score_memory(prompt: str) -> str:
    match = _MEMORY_VALUE_RE.search(prompt)
    if not match:
        return ""
    return str(_safe_int(match.group(2)))


def _predict(category: str, prompt: str) -> str:
    category_norm = _normalize_text(category)
    if category_norm == "math":
        return _score_math(prompt)
    if category_norm == "code":
        return _score_code(prompt)
    if category_norm == "reasoning":
        return _score_reasoning(prompt)
    if category_norm == "safety":
        return _score_safety(prompt)
    if category_norm == "routing_intent":
        return _score_routing(prompt)
    if category_norm == "memory_behavior":
        return _score_memory(prompt)
    return ""


def _validate_row(raw: dict[str, Any], line_number: int) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    missing = [name for name in REQUIRED_FIELDS if name not in raw]
    if missing:
        return None, {
            "line_number": int(line_number),
            "type": "missing_required_fields",
            "details": {"missing": missing},
        }

    if _normalize_text(raw.get("split")) != "holdout":
        return None, None

    case_id = str(raw.get("case_id", "")).strip()
    category = str(raw.get("category", "")).strip()
    prompt = str(raw.get("prompt", "")).strip()
    source = raw.get("source")
    expected_set = _as_expected_set(raw.get("expected"))

    if not case_id:
        return None, {
            "line_number": int(line_number),
            "type": "invalid_case_id",
            "details": {"case_id": raw.get("case_id")},
        }
    if not category:
        return None, {
            "line_number": int(line_number),
            "type": "invalid_category",
            "details": {"category": raw.get("category")},
        }
    if not prompt:
        return None, {
            "line_number": int(line_number),
            "type": "invalid_prompt",
            "details": {"prompt": raw.get("prompt")},
        }
    if not expected_set:
        return None, {
            "line_number": int(line_number),
            "type": "invalid_expected",
            "details": {"expected": raw.get("expected")},
        }
    if not isinstance(source, dict) or not source:
        return None, {
            "line_number": int(line_number),
            "type": "invalid_source_metadata",
            "details": {"source": source},
        }

    return {
        "line_number": int(line_number),
        "case_id": case_id,
        "category": category,
        "prompt": prompt,
        "expected_raw": raw.get("expected"),
        "expected_set": sorted(expected_set),
        "source": dict(source),
    }, None


def _load_cases(dataset_path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    cases: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    skipped_non_holdout = 0
    seen_case_ids: set[str] = set()

    if not dataset_path.exists():
        return [], [{"line_number": 0, "type": "dataset_missing", "details": {"path": str(dataset_path)}}], 0

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

        if not isinstance(payload, dict):
            errors.append(
                {
                    "line_number": int(line_number),
                    "type": "invalid_row_type",
                    "details": {"row_type": type(payload).__name__},
                }
            )
            continue

        case, row_error = _validate_row(payload, line_number)
        if row_error is not None:
            errors.append(row_error)
            continue
        if case is None:
            skipped_non_holdout += 1
            continue

        case_id = str(case["case_id"])
        if case_id in seen_case_ids:
            errors.append(
                {
                    "line_number": int(line_number),
                    "type": "duplicate_case_id",
                    "details": {"case_id": case_id},
                }
            )
            continue

        seen_case_ids.add(case_id)
        cases.append(case)

    cases.sort(key=lambda row: (str(row["case_id"]), int(row["line_number"])))
    return cases, errors, int(skipped_non_holdout)


def _category_metrics(rows: list[dict[str, Any]]) -> dict[str, dict[str, float | int]]:
    grouped: dict[str, dict[str, int]] = {}
    for row in rows:
        category = str(row.get("category", "uncategorized"))
        block = grouped.setdefault(category, {"num_cases": 0, "passed": 0})
        block["num_cases"] += 1
        if bool(row.get("pass", False)):
            block["passed"] += 1

    result: dict[str, dict[str, float | int]] = {}
    for category in sorted(grouped):
        num_cases = int(grouped[category]["num_cases"])
        passed = int(grouped[category]["passed"])
        result[category] = {
            "num_cases": num_cases,
            "passed": passed,
            "pass_rate": float(passed / max(1, num_cases)),
        }
    return result


def _resolve_path(repo_root: Path, value: str) -> Path:
    candidate = Path(value)
    if candidate.is_absolute():
        return candidate.resolve()
    return (repo_root / candidate).resolve()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic scoring over external holdout benchmark rows.")
    parser.add_argument("--dataset", default="datasets/external_benchmarks.jsonl")
    parser.add_argument("--output", default="reports/external_bench.json")
    parser.add_argument("--max-error-details", type=int, default=50)
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    dataset_path = _resolve_path(repo_root, str(args.dataset))
    output_path = _resolve_path(repo_root, str(args.output))

    cases, errors, skipped_non_holdout = _load_cases(dataset_path)
    results: list[dict[str, Any]] = []
    for case in cases:
        prediction = _predict(str(case["category"]), str(case["prompt"]))
        prediction_norm = _normalize_answer(prediction)
        expected_set = {str(value) for value in case["expected_set"]}
        passed = bool(prediction_norm in expected_set)
        results.append(
            {
                "case_id": str(case["case_id"]),
                "category": str(case["category"]),
                "pass": bool(passed),
                "prediction": str(prediction),
                "expected": case["expected_raw"],
                "source": dict(case["source"]),
            }
        )

    num_cases = int(len(cases))
    scored_cases = int(len(results))
    passed_cases = int(sum(1 for row in results if bool(row.get("pass", False))))
    pass_rate = float(passed_cases / max(1, scored_cases))

    malformed_rows = int(sum(1 for row in errors if str(row.get("type")) == "malformed_json"))
    counts = {
        "num_cases": int(num_cases),
        "scored_cases": int(scored_cases),
        "passed": int(passed_cases),
        "invalid_rows": int(len(errors)),
        "malformed_rows": int(malformed_rows),
        "skipped_non_holdout": int(skipped_non_holdout),
    }
    metrics = {
        "pass_rate": float(pass_rate),
        "by_category": _category_metrics(results),
    }

    status = "pass" if num_cases > 0 else "fail"
    report = {
        "suite": "external_holdout_bench",
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "dataset": {
            "path": str(dataset_path),
            "split": "holdout",
        },
        "deterministic_scoring": {
            "version": "rule_based_v1",
            "order": "case_id_ascending",
        },
        "counts": counts,
        "num_cases": int(counts["num_cases"]),
        "scored_cases": int(counts["scored_cases"]),
        "passed": int(counts["passed"]),
        "pass_rate": float(pass_rate),
        "metrics": metrics,
        "errors": errors[: max(0, int(args.max_error_details))],
        "cases": results,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Wrote {output_path}")
    return 0 if status == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
