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
            "eval_shadow_prod.py",
            "--dataset",
            str(dataset_path),
            "--output",
            str(out_path),
        ],
    )
    exit_code = module.main()
    assert exit_code == 0
    return json.loads(out_path.read_text(encoding="utf-8"))


def test_shadow_prod_dataset_shape() -> None:
    dataset_path = Path(__file__).resolve().parents[1] / "datasets" / "benchmark_shadow_prod.jsonl"
    assert dataset_path.exists()

    rows = [json.loads(line) for line in dataset_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(rows) >= 150
    assert all(str(row.get("traffic_slice", "")).strip() for row in rows)


def test_shadow_eval_schema_and_delta(tmp_path, monkeypatch) -> None:
    module = _load_script_module("eval_shadow_prod_script", "eval_shadow_prod.py")
    dataset_path = Path(__file__).resolve().parents[1] / "datasets" / "benchmark_shadow_prod.jsonl"

    payload_a = _run_eval(module, tmp_path / "shadow_a.json", monkeypatch, dataset_path=dataset_path)
    payload_b = _run_eval(module, tmp_path / "shadow_b.json", monkeypatch, dataset_path=dataset_path)

    assert payload_a == payload_b
    assert payload_a["suite"] == "shadow_prod_eval"
    assert payload_a["schema_version"] == "1.1"
    assert payload_a["status"] == "pass"

    counts = payload_a["counts"]
    assert counts["num_cases"] >= 150

    metrics = payload_a["metrics"]
    assert float(metrics["pass_rate_delta_vs_baseline"]) >= 0.02
    assert float(metrics["worst_segment_pass_rate"]) >= 0.60
    assert len(metrics["by_segment"]) >= 3

    assert payload_a["checks"]["delta_vs_baseline"] is True
    assert payload_a["checks"]["worst_segment_floor"] is True
