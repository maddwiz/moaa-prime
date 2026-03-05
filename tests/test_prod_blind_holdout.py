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


def _run_eval(module, out_path: Path, monkeypatch, *, dataset_path: Path) -> dict:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "eval_blind_holdout.py",
            "--dataset",
            str(dataset_path),
            "--output",
            str(out_path),
        ],
    )
    exit_code = module.main()
    assert exit_code == 0
    return json.loads(out_path.read_text(encoding="utf-8"))


def test_blind_holdout_dataset_shape() -> None:
    dataset_path = Path(__file__).resolve().parents[1] / "datasets" / "benchmark_holdout_locked.jsonl"
    assert dataset_path.exists()

    rows = [json.loads(line) for line in dataset_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(rows) >= 250

    splits = {str(row.get("split", "")) for row in rows}
    categories = {str(row.get("category", "")) for row in rows}
    assert splits == {"holdout_locked"}
    assert categories == {"math", "code", "reasoning", "safety", "routing_intent", "memory_behavior"}


def test_blind_holdout_eval_schema_and_determinism(tmp_path, monkeypatch) -> None:
    module = _load_script_module("eval_blind_holdout_script", "eval_blind_holdout.py")
    dataset_path = Path(__file__).resolve().parents[1] / "datasets" / "benchmark_holdout_locked.jsonl"

    payload_a = _run_eval(module, tmp_path / "blind_a.json", monkeypatch, dataset_path=dataset_path)
    payload_b = _run_eval(module, tmp_path / "blind_b.json", monkeypatch, dataset_path=dataset_path)

    assert payload_a == payload_b
    assert payload_a["suite"] == "blind_holdout"
    assert payload_a["schema_version"] == "1.1"
    assert payload_a["status"] == "pass"

    counts = payload_a["counts"]
    assert counts["num_cases"] >= 250
    assert counts["num_cases"] == payload_a["num_cases"]
    assert counts["scored_cases"] == payload_a["scored_cases"]
    assert counts["passed"] == payload_a["passed"]
    assert counts["num_cases"] >= counts["scored_cases"] >= counts["passed"] >= 0

    metrics = payload_a["metrics"]
    assert float(metrics["pass_rate"]) >= 0.72
    assert float(metrics["worst_category_pass_rate"]) >= 0.60
    assert float(metrics["latency_p95_ms"]) > 0.0

    summary = payload_a["summary"]
    assert summary["counts"]["num_cases"] == counts["num_cases"]
    assert float(summary["metrics"]["pass_rate"]) == float(metrics["pass_rate"])
    assert payload_a["checks"]["pass_rate_floor"] is True
    assert payload_a["checks"]["worst_category_floor"] is True
