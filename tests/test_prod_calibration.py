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


def _run_calibration(module, out_path: Path, monkeypatch) -> dict:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "eval_calibration.py",
            "--output",
            str(out_path),
        ],
    )
    exit_code = module.main()
    assert exit_code == 0
    return json.loads(out_path.read_text(encoding="utf-8"))


def test_prod_calibration_eval_schema_and_metrics(tmp_path, monkeypatch) -> None:
    module = _load_script_module("eval_calibration_script", "eval_calibration.py")

    payload_a = _run_calibration(module, tmp_path / "calibration_a.json", monkeypatch)
    payload_b = _run_calibration(module, tmp_path / "calibration_b.json", monkeypatch)

    assert payload_a == payload_b
    assert payload_a["suite"] == "prod_calibration"
    assert payload_a["schema_version"] == "1.1"
    assert payload_a["status"] == "pass"

    counts = payload_a["counts"]
    assert counts["num_cases"] >= 100
    assert counts["num_cases"] == payload_a["num_cases"]
    assert counts["scored_cases"] == payload_a["scored_cases"]
    assert counts["passed"] == payload_a["passed"]

    metrics = payload_a["metrics"]
    assert float(metrics["ece"]) <= 0.12
    assert float(metrics["brier_score"]) <= 0.25
    assert payload_a["checks"]["ece_within_budget"] is True
    assert payload_a["checks"]["brier_within_budget"] is True

    bins = payload_a["bins"]
    assert isinstance(bins, list)
    assert len(bins) == int(payload_a["config"]["bins"])
    assert sum(int(block["count"]) for block in bins) == counts["num_cases"]
