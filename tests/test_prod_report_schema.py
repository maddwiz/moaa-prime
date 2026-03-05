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


def _run_preflight(module, out_path: Path, monkeypatch) -> dict:
    monkeypatch.setenv("MOAA_LLM_PROVIDER", "stub")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "preflight_prod.py",
            "--output",
            str(out_path),
            "--cli-timeout-sec",
            "15",
            "--runtime-timeout-sec",
            "15",
        ],
    )
    assert module.main() == 0
    return json.loads(out_path.read_text(encoding="utf-8"))


def _run_load(module, out_path: Path, monkeypatch, *, iters: int) -> dict:
    monkeypatch.setenv("MOAA_LLM_PROVIDER", "stub")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "load_smoke.py",
            "--output",
            str(out_path),
            "--iters",
            str(iters),
            "--timeout-sec",
            "15",
            "--max-retries",
            "1",
        ],
    )
    assert module.main() == 0
    return json.loads(out_path.read_text(encoding="utf-8"))


def _assert_common_report_schema(payload: dict) -> None:
    assert payload["schema_version"] == "1.1"
    assert "status" in payload
    assert payload["status"] in {"pass", "fail"}
    assert isinstance(payload["counts"], dict)
    assert payload["num_cases"] == payload["counts"]["num_cases"]
    assert payload["scored_cases"] == payload["counts"]["scored_cases"]
    assert payload["passed"] == payload["counts"]["passed"]
    assert payload["num_cases"] >= payload["scored_cases"] >= payload["passed"] >= 0
    assert isinstance(payload["pass_rate"], float)


def test_prod_reports_share_stable_schema_and_deterministic_stub_metrics(tmp_path, monkeypatch) -> None:
    preflight_module = _load_script_module("preflight_prod_schema_script", "preflight_prod.py")
    load_module = _load_script_module("load_smoke_schema_script", "load_smoke.py")

    preflight_path_a = tmp_path / "reports" / "preflight_a.json"
    preflight_path_b = tmp_path / "reports" / "preflight_b.json"
    preflight_a = _run_preflight(preflight_module, preflight_path_a, monkeypatch)
    preflight_b = _run_preflight(preflight_module, preflight_path_b, monkeypatch)
    _assert_common_report_schema(preflight_a)
    _assert_common_report_schema(preflight_b)
    assert [row["name"] for row in preflight_a["checks"]] == [row["name"] for row in preflight_b["checks"]]
    assert [row["status"] for row in preflight_a["checks"]] == [row["status"] for row in preflight_b["checks"]]

    load_path_a = tmp_path / "reports" / "load_a.json"
    load_path_b = tmp_path / "reports" / "load_b.json"
    load_a = _run_load(load_module, load_path_a, monkeypatch, iters=10)
    load_b = _run_load(load_module, load_path_b, monkeypatch, iters=10)
    _assert_common_report_schema(load_a)
    _assert_common_report_schema(load_b)

    assert load_a["metrics"] == load_b["metrics"]
    latencies_a = [float((row.get("details", {}) or {}).get("latency_ms", 0.0)) for row in load_a["samples"]]
    latencies_b = [float((row.get("details", {}) or {}).get("latency_ms", 0.0)) for row in load_b["samples"]]
    assert latencies_a == latencies_b
