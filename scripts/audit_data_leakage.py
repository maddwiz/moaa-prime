from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping


SCHEMA_VERSION = "1.1"
SUITE = "leakage_audit"
MAX_EXACT_OVERLAP = 0.01
MAX_NEAR_OVERLAP = 0.03
NEAR_SIMILARITY_THRESHOLD = 0.92

_WHITESPACE_RE = re.compile(r"\s+")


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


def _normalize_prompt(text: Any) -> str:
    return _WHITESPACE_RE.sub(" ", str(text or "").strip().lower())


def _char_ngrams(text: str, *, n: int) -> set[str]:
    if n <= 1:
        return {text} if text else set()
    if len(text) < n:
        return {text} if text else set()
    return {text[i : i + n] for i in range(0, len(text) - n + 1)}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    overlap = len(a & b)
    union = len(a | b)
    if union <= 0:
        return 0.0
    return float(overlap / union)


def _load_prompts(path: Path, *, split: str | None = None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    if not path.exists():
        return [], [{"line_number": 0, "type": "dataset_missing", "details": {"path": str(path)}}]

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

        row_split = str(payload.get("split", "") or "").strip().lower()
        if split is not None and row_split != str(split).strip().lower():
            continue

        case_id = str(payload.get("case_id", "") or "").strip() or f"line_{line_number}"
        prompt = _normalize_prompt(payload.get("prompt"))
        if not prompt:
            errors.append(
                {
                    "line_number": int(line_number),
                    "type": "invalid_prompt",
                    "details": {"case_id": case_id},
                }
            )
            continue

        rows.append(
            {
                "case_id": case_id,
                "split": row_split,
                "prompt": prompt,
            }
        )

    return rows, errors


def _overlap_rate(*, matches: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return float(matches / denominator)


def _sample(items: Iterable[dict[str, Any]], *, limit: int) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in items:
        out.append(dict(row))
        if len(out) >= max(0, int(limit)):
            break
    return out


def _compute_exact_overlap(*, holdout: list[dict[str, Any]], reference: list[dict[str, Any]]) -> tuple[int, list[dict[str, Any]]]:
    reference_by_prompt: dict[str, list[str]] = {}
    for row in reference:
        reference_by_prompt.setdefault(str(row["prompt"]), []).append(str(row["case_id"]))

    matches = 0
    examples: list[dict[str, Any]] = []
    for row in holdout:
        prompt = str(row["prompt"])
        ref_ids = reference_by_prompt.get(prompt)
        if not ref_ids:
            continue
        matches += 1
        examples.append(
            {
                "holdout_case_id": str(row["case_id"]),
                "reference_case_ids": list(ref_ids[:3]),
            }
        )
    return matches, examples


def _compute_near_overlap(
    *,
    holdout: list[dict[str, Any]],
    reference: list[dict[str, Any]],
    threshold: float,
) -> tuple[int, list[dict[str, Any]]]:
    if not holdout or not reference:
        return 0, []

    ref_grams = [
        {
            "case_id": str(row["case_id"]),
            "prompt": str(row["prompt"]),
            "grams": _char_ngrams(str(row["prompt"]), n=5),
        }
        for row in reference
    ]

    near_matches = 0
    examples: list[dict[str, Any]] = []

    for row in holdout:
        holdout_prompt = str(row["prompt"])
        holdout_grams = _char_ngrams(holdout_prompt, n=5)
        best_similarity = 0.0
        best_case_id = ""
        for candidate in ref_grams:
            sim = _jaccard(holdout_grams, set(candidate["grams"]))
            if sim > best_similarity:
                best_similarity = sim
                best_case_id = str(candidate["case_id"])
        if best_similarity >= float(threshold):
            near_matches += 1
            examples.append(
                {
                    "holdout_case_id": str(row["case_id"]),
                    "reference_case_id": best_case_id,
                    "similarity": float(best_similarity),
                }
            )

    return near_matches, examples


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit exact and near-duplicate leakage between training/tuning corpora and locked holdout.")
    parser.add_argument("--train-dataset", default="datasets/benchmark_train.jsonl")
    parser.add_argument("--tuning-dataset", default="datasets/tough_benchmarks.jsonl")
    parser.add_argument("--holdout-dataset", default="datasets/benchmark_holdout_locked.jsonl")
    parser.add_argument("--output", default="reports/leakage_audit.json")
    parser.add_argument("--max-exact-overlap", type=float, default=MAX_EXACT_OVERLAP)
    parser.add_argument("--max-near-overlap", type=float, default=MAX_NEAR_OVERLAP)
    parser.add_argument("--near-similarity-threshold", type=float, default=NEAR_SIMILARITY_THRESHOLD)
    parser.add_argument("--max-example-details", type=int, default=30)
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    train_path = _resolve_path(repo_root, str(args.train_dataset))
    tuning_path = _resolve_path(repo_root, str(args.tuning_dataset))
    holdout_path = _resolve_path(repo_root, str(args.holdout_dataset))
    output_path = _resolve_path(repo_root, str(args.output))

    train_rows, train_errors = _load_prompts(train_path)
    tuning_rows, tuning_errors = _load_prompts(tuning_path)
    holdout_rows, holdout_errors = _load_prompts(holdout_path, split="holdout_locked")

    exact_train_count, exact_train_examples = _compute_exact_overlap(holdout=holdout_rows, reference=train_rows)
    exact_tuning_count, exact_tuning_examples = _compute_exact_overlap(holdout=holdout_rows, reference=tuning_rows)
    exact_union_count, exact_union_examples = _compute_exact_overlap(
        holdout=holdout_rows,
        reference=train_rows + tuning_rows,
    )

    near_train_count, near_train_examples = _compute_near_overlap(
        holdout=holdout_rows,
        reference=train_rows,
        threshold=float(args.near_similarity_threshold),
    )
    near_tuning_count, near_tuning_examples = _compute_near_overlap(
        holdout=holdout_rows,
        reference=tuning_rows,
        threshold=float(args.near_similarity_threshold),
    )
    near_union_count, near_union_examples = _compute_near_overlap(
        holdout=holdout_rows,
        reference=train_rows + tuning_rows,
        threshold=float(args.near_similarity_threshold),
    )

    holdout_count = int(len(holdout_rows))
    exact_train_rate = _overlap_rate(matches=exact_train_count, denominator=holdout_count)
    exact_tuning_rate = _overlap_rate(matches=exact_tuning_count, denominator=holdout_count)
    exact_union_rate = _overlap_rate(matches=exact_union_count, denominator=holdout_count)

    near_train_rate = _overlap_rate(matches=near_train_count, denominator=holdout_count)
    near_tuning_rate = _overlap_rate(matches=near_tuning_count, denominator=holdout_count)
    near_union_rate = _overlap_rate(matches=near_union_count, denominator=holdout_count)

    max_exact_overlap = float(max(exact_train_rate, exact_tuning_rate, exact_union_rate))
    max_near_overlap = float(max(near_train_rate, near_tuning_rate, near_union_rate))

    checks = {
        "exact_overlap_within_threshold": bool(max_exact_overlap <= float(args.max_exact_overlap)),
        "near_overlap_within_threshold": bool(max_near_overlap <= float(args.max_near_overlap)),
    }
    checks["exact_overlap_within_budget"] = bool(checks["exact_overlap_within_threshold"])
    checks["near_overlap_within_budget"] = bool(checks["near_overlap_within_threshold"])
    status = "pass" if holdout_count > 0 and all(checks.values()) else "fail"

    counts = {
        "num_holdout_cases": holdout_count,
        "num_train_cases": int(len(train_rows)),
        "num_tuning_cases": int(len(tuning_rows)),
        "num_reference_cases": int(len(train_rows) + len(tuning_rows)),
        "exact_overlaps_union": int(exact_union_count),
        "near_overlaps_union": int(near_union_count),
    }

    metrics = {
        "near_similarity_threshold": float(args.near_similarity_threshold),
        "max_exact_overlap_allowed": float(args.max_exact_overlap),
        "max_near_overlap_allowed": float(args.max_near_overlap),
        "exact_overlap_rate_train": float(exact_train_rate),
        "exact_overlap_rate_tuning": float(exact_tuning_rate),
        "exact_overlap_rate_union": float(exact_union_rate),
        "near_overlap_rate_train": float(near_train_rate),
        "near_overlap_rate_tuning": float(near_tuning_rate),
        "near_overlap_rate_union": float(near_union_rate),
        "max_exact_overlap": float(max_exact_overlap),
        "max_near_overlap": float(max_near_overlap),
    }

    payload = {
        "suite": SUITE,
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "inputs": {
            "train_dataset": str(train_path),
            "tuning_dataset": str(tuning_path),
            "holdout_dataset": str(holdout_path),
        },
        "summary": {
            "counts": counts,
            "metrics": metrics,
            "checks": checks,
        },
        "checks": checks,
        "counts": counts,
        "metrics": metrics,
        "errors": {
            "train": train_errors[: max(0, int(args.max_example_details))],
            "tuning": tuning_errors[: max(0, int(args.max_example_details))],
            "holdout": holdout_errors[: max(0, int(args.max_example_details))],
        },
        "examples": {
            "exact_train": _sample(exact_train_examples, limit=int(args.max_example_details)),
            "exact_tuning": _sample(exact_tuning_examples, limit=int(args.max_example_details)),
            "exact_union": _sample(exact_union_examples, limit=int(args.max_example_details)),
            "near_train": _sample(near_train_examples, limit=int(args.max_example_details)),
            "near_tuning": _sample(near_tuning_examples, limit=int(args.max_example_details)),
            "near_union": _sample(near_union_examples, limit=int(args.max_example_details)),
        },
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {output_path}")
    return 0 if status == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
