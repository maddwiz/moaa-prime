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


def test_prod_preflight_report_passes_with_stub_provider(tmp_path, monkeypatch) -> None:
    module = _load_script_module("preflight_prod_script", "preflight_prod.py")
    out_path = tmp_path / "reports" / "preflight_prod.json"

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

    exit_code = module.main()
    assert exit_code == 0
    assert out_path.exists()

    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["suite"] == "prod_preflight"
    assert payload["schema_version"] == "1.1"
    assert payload["status"] == "pass"
    assert payload["counts"]["num_cases"] == payload["num_cases"]
    assert payload["counts"]["scored_cases"] == payload["scored_cases"]
    assert payload["counts"]["passed"] == payload["passed"]
    assert payload["pass_rate"] == 1.0

    checks = payload["checks"]
    assert isinstance(checks, list)
    assert checks
    names = {str(row.get("name", "")) for row in checks}
    assert {
        "python_version",
        "provider_env",
        "provider_wiring",
        "reports_filesystem",
        "cli_health",
        "runtime_smoke",
    }.issubset(names)
    assert all(str(row.get("status", "")) == "pass" for row in checks)
