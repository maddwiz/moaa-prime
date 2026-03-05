from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


def _load_script_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "eval_external_bench.py"
    spec = importlib.util.spec_from_file_location("eval_external_bench_script", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_eval(module, monkeypatch, *, dataset_path: Path, output_path: Path) -> dict:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "eval_external_bench.py",
            "--dataset",
            str(dataset_path),
            "--output",
            str(output_path),
        ],
    )
    exit_code = module.main()
    assert exit_code == 0
    return json.loads(output_path.read_text(encoding="utf-8"))


def test_external_bench_dataset_has_holdout_rows_with_source_metadata() -> None:
    dataset_path = Path(__file__).resolve().parents[1] / "datasets" / "external_benchmarks.jsonl"
    assert dataset_path.exists()

    rows: list[dict] = []
    for line in dataset_path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text:
            continue
        row = json.loads(text)
        assert isinstance(row, dict)
        rows.append(row)

    assert len(rows) >= 100
    assert len({str(row.get("case_id", "")) for row in rows}) == len(rows)
    for row in rows:
        assert row.get("split") == "holdout"
        assert isinstance(row.get("case_id"), str) and row["case_id"].strip()
        assert isinstance(row.get("category"), str) and row["category"].strip()
        assert isinstance(row.get("prompt"), str) and row["prompt"].strip()
        assert "expected" in row
        assert isinstance(row.get("source"), dict) and row["source"]


def test_external_bench_eval_report_is_deterministic_and_schema_stable(tmp_path, monkeypatch) -> None:
    module = _load_script_module()
    dataset_path = Path(__file__).resolve().parents[1] / "datasets" / "external_benchmarks.jsonl"

    payload_a = _run_eval(module, monkeypatch, dataset_path=dataset_path, output_path=tmp_path / "report_a.json")
    payload_b = _run_eval(module, monkeypatch, dataset_path=dataset_path, output_path=tmp_path / "report_b.json")

    assert payload_a == payload_b
    assert payload_a["suite"] == "external_holdout_bench"
    assert payload_a["schema_version"] == "1.1"
    assert payload_a["status"] == "pass"
    assert payload_a["counts"]["num_cases"] >= 100
    assert payload_a["counts"]["num_cases"] == payload_a["num_cases"]
    assert payload_a["counts"]["scored_cases"] == payload_a["scored_cases"]
    assert payload_a["counts"]["passed"] == payload_a["passed"]
    assert payload_a["counts"]["num_cases"] >= payload_a["counts"]["scored_cases"] >= payload_a["counts"]["passed"] >= 0
    assert isinstance(payload_a["metrics"], dict)
    assert isinstance(payload_a["metrics"]["pass_rate"], float)
    assert payload_a["metrics"]["pass_rate"] == payload_a["pass_rate"]
    assert payload_a["deterministic_scoring"]["version"] == "rule_based_v1"
    assert payload_a["deterministic_scoring"]["order"] == "case_id_ascending"
    assert isinstance(payload_a["cases"], list)
    assert len(payload_a["cases"]) == payload_a["counts"]["scored_cases"]
    assert all("source" in row and isinstance(row["source"], dict) for row in payload_a["cases"])


def test_external_bench_eval_handles_malformed_rows_deterministically(tmp_path, monkeypatch) -> None:
    module = _load_script_module()
    dataset_path = tmp_path / "external_fixture.jsonl"
    output_path = tmp_path / "report.json"

    lines = [
        json.dumps(
            {
                "case_id": "holdout_math_ok",
                "category": "math",
                "prompt": "Compute 2 + 2. Reply with only the number.",
                "expected": "4",
                "split": "holdout",
                "source": {"name": "fixture"},
            }
        ),
        "{not-json}",
        json.dumps(["bad", "row", "type"]),
        json.dumps(
            {
                "case_id": "missing_source",
                "category": "math",
                "prompt": "Compute 5 + 5. Reply with only the number.",
                "expected": "10",
                "split": "holdout",
            }
        ),
        json.dumps(
            {
                "case_id": "skipped_train_row",
                "category": "math",
                "prompt": "Compute 3 + 3. Reply with only the number.",
                "expected": "6",
                "split": "train",
                "source": {"name": "fixture"},
            }
        ),
        json.dumps(
            {
                "case_id": "holdout_math_ok",
                "category": "math",
                "prompt": "Compute 9 + 9. Reply with only the number.",
                "expected": "18",
                "split": "holdout",
                "source": {"name": "fixture"},
            }
        ),
    ]
    dataset_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "eval_external_bench.py",
            "--dataset",
            str(dataset_path),
            "--output",
            str(output_path),
        ],
    )

    exit_code = module.main()
    assert exit_code == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert payload["status"] == "pass"
    assert payload["counts"]["num_cases"] == 1
    assert payload["counts"]["scored_cases"] == 1
    assert payload["counts"]["passed"] == 1
    assert payload["counts"]["invalid_rows"] == 4
    assert payload["counts"]["malformed_rows"] == 1
    assert payload["counts"]["skipped_non_holdout"] == 1
    assert payload["metrics"]["pass_rate"] == 1.0

    error_types = [str(row.get("type", "")) for row in payload["errors"]]
    assert error_types == [
        "malformed_json",
        "invalid_row_type",
        "missing_required_fields",
        "duplicate_case_id",
    ]
