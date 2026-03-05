from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


def _load_script_module(module_name: str, script_name: str):
    script_path = Path(__file__).resolve().parents[1] / "scripts" / script_name
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_audit(module, out_path: Path, monkeypatch, *, train_path: Path, holdout_path: Path) -> tuple[int, dict]:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "audit_data_leakage.py",
            "--train-dataset",
            str(train_path),
            "--holdout-dataset",
            str(holdout_path),
            "--output",
            str(out_path),
        ],
    )
    exit_code = module.main()
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    return exit_code, payload


def test_leakage_audit_schema_and_determinism(tmp_path, monkeypatch) -> None:
    module = _load_script_module("audit_data_leakage_script", "audit_data_leakage.py")
    repo_root = Path(__file__).resolve().parents[1]
    train_path = repo_root / "datasets" / "benchmark_train.jsonl"
    holdout_path = repo_root / "datasets" / "benchmark_holdout_locked.jsonl"

    exit_a, payload_a = _run_audit(
        module,
        tmp_path / "leakage_a.json",
        monkeypatch,
        train_path=train_path,
        holdout_path=holdout_path,
    )
    exit_b, payload_b = _run_audit(
        module,
        tmp_path / "leakage_b.json",
        monkeypatch,
        train_path=train_path,
        holdout_path=holdout_path,
    )

    assert exit_a == 0
    assert exit_b == 0
    assert payload_a == payload_b
    assert payload_a["suite"] == "leakage_audit"
    assert payload_a["schema_version"] == "1.1"
    assert payload_a["status"] == "pass"

    metrics = payload_a["metrics"]
    assert float(metrics["max_exact_overlap"]) <= 0.01
    assert float(metrics["max_near_overlap"]) <= 0.03
    assert payload_a["checks"]["exact_overlap_within_budget"] is True
    assert payload_a["checks"]["near_overlap_within_budget"] is True
    assert int(payload_a["counts"]["num_holdout_cases"]) >= 250


def test_leakage_audit_fails_on_exact_overlap(tmp_path, monkeypatch) -> None:
    module = _load_script_module("audit_data_leakage_fail_script", "audit_data_leakage.py")

    train_path = tmp_path / "train.jsonl"
    holdout_path = tmp_path / "holdout.jsonl"
    out_path = tmp_path / "leakage_fail.json"

    shared = {
        "case_id": "dup_case",
        "category": "math",
        "prompt": "Compute 2 + 2. Reply with only the number.",
        "expected": "4",
    }
    train_path.write_text(
        "\n".join(
            [
                json.dumps({**shared, "split": "train"}),
                json.dumps({"case_id": "train_2", "category": "math", "prompt": "Compute 5 + 5", "expected": "10", "split": "train"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    holdout_path.write_text(json.dumps({**shared, "split": "holdout_locked"}) + "\n", encoding="utf-8")

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "audit_data_leakage.py",
            "--train-dataset",
            str(train_path),
            "--holdout-dataset",
            str(holdout_path),
            "--output",
            str(out_path),
            "--max-exact-overlap",
            "0.0",
            "--max-near-overlap",
            "0.0",
        ],
    )
    exit_code = module.main()
    payload = json.loads(out_path.read_text(encoding="utf-8"))

    assert exit_code == 2
    assert payload["status"] == "fail"
    assert payload["checks"]["exact_overlap_within_budget"] is False
    assert float(payload["metrics"]["max_exact_overlap"]) > 0.0
