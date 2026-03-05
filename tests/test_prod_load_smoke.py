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


def _run_load_smoke(module, out_path: Path, monkeypatch, *, iters: int) -> dict:
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
    exit_code = module.main()
    assert exit_code == 0
    return json.loads(out_path.read_text(encoding="utf-8"))


def test_prod_load_smoke_report_meets_budget_with_stub_provider(tmp_path, monkeypatch) -> None:
    module = _load_script_module("load_smoke_script", "load_smoke.py")
    out_path = tmp_path / "reports" / "load_smoke.json"
    payload = _run_load_smoke(module, out_path, monkeypatch, iters=12)

    assert payload["suite"] == "prod_load_smoke"
    assert payload["schema_version"] == "1.1"
    assert payload["status"] == "pass"
    assert payload["provider"] == "stub"
    assert payload["counts"]["num_cases"] == 12
    assert payload["counts"]["scored_cases"] == 12
    assert payload["counts"]["passed"] == payload["metrics"]["successes"]

    metrics = payload["metrics"]
    assert metrics["request_count"] == 12
    assert metrics["failures"] <= 1
    assert metrics["error_rate"] <= 0.01
    assert metrics["p95_latency_ms"] <= 2500.0
    assert payload["checks"]["error_rate_within_budget"] is True
    assert payload["checks"]["p95_latency_within_budget"] is True

    samples = payload["samples"]
    assert len(samples) == 12
    assert all(isinstance(row["success"], bool) for row in samples)
