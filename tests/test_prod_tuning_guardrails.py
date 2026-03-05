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


def _run_tuning(module, out_path: Path, monkeypatch) -> dict:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "tune_production.py",
            "--output",
            str(out_path),
        ],
    )
    exit_code = module.main()
    assert exit_code == 0
    return json.loads(out_path.read_text(encoding="utf-8"))


def test_prod_tuning_guardrails_and_determinism(tmp_path, monkeypatch) -> None:
    module = _load_script_module("tune_production_script", "tune_production.py")

    payload_a = _run_tuning(module, tmp_path / "tuning_a.json", monkeypatch)
    payload_b = _run_tuning(module, tmp_path / "tuning_b.json", monkeypatch)

    assert payload_a == payload_b
    assert payload_a["suite"] == "tuning_report"
    assert payload_a["schema_version"] == "1.1"
    assert payload_a["status"] == "pass"

    explored = payload_a["explored_configs"]
    assert isinstance(explored, list)
    assert len(explored) >= 20
    assert all("config_id" in row and row["config_id"] for row in explored)

    best = payload_a["best_config"]
    assert isinstance(best, dict)
    assert isinstance(best["config_id"], str) and best["config_id"].strip()
    assert best["safe"] is True

    ids = {str(row["config_id"]) for row in explored}
    assert best["config_id"] in ids

    baseline = payload_a["baseline"]
    assert float(best["objective_score"]) >= float(baseline["objective_score"])
    assert float(best["metrics"]["pass_rate"]) >= 0.75
    assert float(best["metrics"]["by_split"]["adversarial"]["pass_rate"]) >= 0.60
    assert float(best["metrics"]["by_split"]["ood"]["pass_rate"]) >= 0.65
    assert float(best["metrics"]["worst_category_pass_rate"]) >= 0.60
