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


def _run_stability(module, out_path: Path, monkeypatch, *, seeds: int) -> dict:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "eval_stability.py",
            "--output",
            str(out_path),
            "--seeds",
            str(seeds),
        ],
    )
    exit_code = module.main()
    assert exit_code == 0
    return json.loads(out_path.read_text(encoding="utf-8"))


def test_prod_stability_eval_schema_and_budget(tmp_path, monkeypatch) -> None:
    module = _load_script_module("eval_stability_script", "eval_stability.py")

    payload_a = _run_stability(module, tmp_path / "stability_a.json", monkeypatch, seeds=10)
    payload_b = _run_stability(module, tmp_path / "stability_b.json", monkeypatch, seeds=10)

    assert payload_a == payload_b
    assert payload_a["suite"] == "prod_stability"
    assert payload_a["schema_version"] == "1.1"
    assert payload_a["status"] == "pass"

    counts = payload_a["counts"]
    assert counts["num_cases"] >= 100
    assert counts["num_cases"] == payload_a["num_cases"]
    assert counts["scored_cases"] == payload_a["scored_cases"]
    assert counts["passed"] == payload_a["passed"]

    metrics = payload_a["metrics"]
    assert metrics["seed_count"] == 10
    assert float(metrics["pass_rate_stddev"]) <= 0.03
    assert float(metrics["oracle_score_stddev"]) <= 0.05

    assert payload_a["checks"]["pass_rate_stddev_within_budget"] is True
    assert payload_a["checks"]["oracle_stddev_within_budget"] is True
    assert len(payload_a["per_seed"]) == 10
