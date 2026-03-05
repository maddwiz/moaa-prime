from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

SCHEMA_VERSION = "1.1"
REQUIRED_FIELDS = ("case_id", "category", "prompt", "expected", "split", "source")
ALLOWED_SPLITS = ("holdout", "adversarial", "ood")
ALLOWED_CATEGORIES = (
    "math",
    "code",
    "reasoning",
    "safety",
    "routing_intent",
    "memory_behavior",
)

_INT_RE = re.compile(r"^[+-]?\d+$")
_FLOAT_RE = re.compile(r"^[+-]?(?:\d+\.\d+|\d+)$")
_MATH_COMPUTE_RE = re.compile(r"compute\s+([+-]?\d+(?:\.\d+)?)\s*([+\-*/])\s*([+-]?\d+(?:\.\d+)?)", re.IGNORECASE)
_MATH_SOLVE_LINEAR_RE = re.compile(r"solve\s+([+-]?\d+(?:\.\d+)?)\s*x\s*=\s*([+-]?\d+(?:\.\d+)?)", re.IGNORECASE)
_LEN_RE = re.compile(r"len\(\s*(['\"])(.*?)\1\s*\)", re.IGNORECASE)
_OLDER_RE = re.compile(
    r"if\s+([A-Za-z][A-Za-z0-9_-]*)\s+is older than\s+([A-Za-z][A-Za-z0-9_-]*)\s+and\s+\2\s+is older than\s+([A-Za-z][A-Za-z0-9_-]*)",
    re.IGNORECASE,
)
_TOKEN_VALUE_RE = re.compile(r"token\s+([A-Za-z0-9_-]+)\s+has value\s+([+-]?\d+(?:\.\d+)?)", re.IGNORECASE)
_TARGET_TOKEN_RE = re.compile(r"for token\s+([A-Za-z0-9_-]+)", re.IGNORECASE)


@dataclass(frozen=True)
class ToughCase:
    line_number: int
    case_id: str
    category: str
    prompt: str
    expected_raw: Any
    expected_set: tuple[str, ...]
    split: str
    source: dict[str, Any]


@dataclass(frozen=True)
class Prediction:
    value: str
    confidence: float


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


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(float(lo), min(float(hi), float(value)))


def normalize_text(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().split())


def normalize_answer(value: Any) -> str:
    text = normalize_text(value)
    if not text:
        return ""
    if _INT_RE.fullmatch(text):
        return str(int(text))
    if _FLOAT_RE.fullmatch(text):
        as_float = _safe_float(text)
        if float(as_float).is_integer():
            return str(int(as_float))
        return f"{as_float:.10g}"
    return text


def as_expected_set(expected: Any) -> set[str]:
    if isinstance(expected, list):
        raw_values = expected
    else:
        raw_values = [expected]
    values = {normalize_answer(item) for item in raw_values}
    return {value for value in values if value}


def _score_math(prompt: str) -> Prediction:
    compute_match = _MATH_COMPUTE_RE.search(prompt)
    if compute_match:
        left = _safe_float(compute_match.group(1))
        op = str(compute_match.group(2))
        right = _safe_float(compute_match.group(3))

        result: float | None = None
        if op == "+":
            result = left + right
        elif op == "-":
            result = left - right
        elif op == "*":
            result = left * right
        elif op == "/" and right != 0.0:
            result = left / right

        if result is None:
            return Prediction(value="", confidence=0.35)
        if float(result).is_integer():
            return Prediction(value=str(int(result)), confidence=0.94)
        return Prediction(value=f"{result:.10g}", confidence=0.91)

    solve_match = _MATH_SOLVE_LINEAR_RE.search(prompt)
    if solve_match:
        coeff = _safe_float(solve_match.group(1))
        rhs = _safe_float(solve_match.group(2))
        if coeff == 0.0:
            return Prediction(value="", confidence=0.30)
        x = rhs / coeff
        if float(x).is_integer():
            return Prediction(value=str(int(x)), confidence=0.90)
        return Prediction(value=f"{x:.10g}", confidence=0.87)

    return Prediction(value="", confidence=0.35)


def _score_code(prompt: str) -> Prediction:
    match = _LEN_RE.search(prompt)
    if not match:
        return Prediction(value="", confidence=0.35)
    token = match.group(2)
    return Prediction(value=str(len(token)), confidence=0.93)


def _score_reasoning(prompt: str) -> Prediction:
    match = _OLDER_RE.search(prompt)
    if not match:
        return Prediction(value="", confidence=0.35)
    return Prediction(value=str(match.group(1)), confidence=0.90)


def _score_safety(prompt: str) -> Prediction:
    text = normalize_text(prompt)
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
        return Prediction(value="unsafe", confidence=0.88)
    return Prediction(value="safe", confidence=0.84)


def _score_routing(prompt: str) -> Prediction:
    prompt_text = str(prompt)
    query_text = prompt_text
    marker = re.search(r"for this query:\s*(.+)$", prompt_text, re.IGNORECASE)
    if marker:
        query_text = marker.group(1)

    text = normalize_text(query_text)

    if any(marker in text for marker in ("python", "function", "code", "script", "def ")):
        return Prediction(value="code", confidence=0.90)
    if any(marker in text for marker in ("remember", "recall", "token", "memory")):
        return Prediction(value="memory", confidence=0.89)
    if any(marker in text for marker in ("if all", "older than", "therefore", "logic", "must", "can a")):
        return Prediction(value="reasoning", confidence=0.87)
    if any(marker in text for marker in ("solve", "compute", "=", "+", "-", "*", "/")):
        return Prediction(value="math", confidence=0.86)
    return Prediction(value="", confidence=0.35)


def _score_memory(prompt: str) -> Prediction:
    pairs = _TOKEN_VALUE_RE.findall(prompt)
    if not pairs:
        return Prediction(value="", confidence=0.35)

    value_by_token: dict[str, str] = {}
    for token, raw_value in pairs:
        value_by_token[str(token)] = normalize_answer(raw_value)

    target_match = _TARGET_TOKEN_RE.search(prompt)
    if target_match:
        token = str(target_match.group(1))
        if token in value_by_token:
            return Prediction(value=value_by_token[token], confidence=0.91)

    fallback_value = normalize_answer(pairs[0][1])
    return Prediction(value=fallback_value, confidence=0.82)


def predict(category: str, prompt: str) -> Prediction:
    category_norm = normalize_text(category)
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
    return Prediction(value="", confidence=0.35)


def _validate_row(
    raw: Mapping[str, Any],
    *,
    line_number: int,
    allowed_splits: set[str],
) -> tuple[ToughCase | None, dict[str, Any] | None]:
    missing = [name for name in REQUIRED_FIELDS if name not in raw]
    if missing:
        return None, {
            "line_number": int(line_number),
            "type": "missing_required_fields",
            "details": {"missing": missing},
        }

    split = normalize_text(raw.get("split"))
    if split not in allowed_splits:
        return None, None

    case_id = str(raw.get("case_id", "")).strip()
    category = normalize_text(raw.get("category"))
    prompt = str(raw.get("prompt", "")).strip()
    source = raw.get("source")
    expected_set = as_expected_set(raw.get("expected"))

    if not case_id:
        return None, {
            "line_number": int(line_number),
            "type": "invalid_case_id",
            "details": {"case_id": raw.get("case_id")},
        }
    if category not in ALLOWED_CATEGORIES:
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

    return (
        ToughCase(
            line_number=int(line_number),
            case_id=case_id,
            category=category,
            prompt=prompt,
            expected_raw=raw.get("expected"),
            expected_set=tuple(sorted(expected_set)),
            split=split,
            source=dict(source),
        ),
        None,
    )


def load_cases(
    dataset_path: Path,
    *,
    allowed_splits: Iterable[str] | None = None,
) -> tuple[list[ToughCase], list[dict[str, Any]], int]:
    allowed = {normalize_text(value) for value in (allowed_splits or ALLOWED_SPLITS)}
    cases: list[ToughCase] = []
    errors: list[dict[str, Any]] = []
    skipped = 0
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

        case, row_error = _validate_row(payload, line_number=line_number, allowed_splits=allowed)
        if row_error is not None:
            errors.append(row_error)
            continue
        if case is None:
            skipped += 1
            continue

        if case.case_id in seen_case_ids:
            errors.append(
                {
                    "line_number": int(line_number),
                    "type": "duplicate_case_id",
                    "details": {"case_id": case.case_id},
                }
            )
            continue

        seen_case_ids.add(case.case_id)
        cases.append(case)

    cases.sort(key=lambda row: (row.case_id, row.line_number))
    return cases, errors, int(skipped)


def _group_metrics(rows: list[Mapping[str, Any]], key: str) -> dict[str, dict[str, float | int]]:
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
            "num_cases": num_cases,
            "passed": passed,
            "pass_rate": float(passed / max(1, num_cases)),
        }
    return out


def evaluate_cases(cases: Iterable[ToughCase]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    for case in cases:
        prediction = predict(case.category, case.prompt)
        prediction_norm = normalize_answer(prediction.value)
        expected_set = {str(value) for value in case.expected_set}
        passed = bool(prediction_norm in expected_set)
        rows.append(
            {
                "case_id": case.case_id,
                "category": case.category,
                "split": case.split,
                "pass": bool(passed),
                "prediction": str(prediction.value),
                "confidence": float(_clamp(prediction.confidence)),
                "expected": case.expected_raw,
                "source": dict(case.source),
            }
        )

    num_cases = int(len(rows))
    scored_cases = int(len(rows))
    passed_cases = int(sum(1 for row in rows if bool(row.get("pass", False))))

    by_split = _group_metrics(rows, "split")
    by_category = _group_metrics(rows, "category")

    populated_categories = [
        float(block["pass_rate"])
        for block in by_category.values()
        if _safe_int(block.get("num_cases"), default=0) > 0
    ]
    worst_category = float(min(populated_categories)) if populated_categories else 0.0

    split_counts = {split: _safe_int(by_split.get(split, {}).get("num_cases"), default=0) for split in ALLOWED_SPLITS}
    category_counts = {
        category: _safe_int(by_category.get(category, {}).get("num_cases"), default=0)
        for category in ALLOWED_CATEGORIES
    }

    split_values = [value for value in split_counts.values() if value > 0]
    category_values = [value for value in category_counts.values() if value > 0]

    metrics = {
        "pass_rate": float(passed_cases / max(1, scored_cases)),
        "by_split": by_split,
        "by_category": by_category,
        "worst_category_pass_rate": float(worst_category),
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
    }

    counts = {
        "num_cases": num_cases,
        "scored_cases": scored_cases,
        "passed": passed_cases,
    }
    return rows, {"counts": counts, "metrics": metrics}
