from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _load_eval_tool_first_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "eval_tool_first.py"
    spec = importlib.util.spec_from_file_location("eval_tool_first_script", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_pr5_eval_tool_first_schema_is_stable_and_non_null(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    module = _load_eval_tool_first_module()

    exit_code_1 = module.main()
    primary_path = tmp_path / "reports" / "tool_first_eval.json"
    compat_path = tmp_path / "reports" / "eval_tool_first.json"
    payload_1 = json.loads(primary_path.read_text(encoding="utf-8"))
    compat_1 = json.loads(compat_path.read_text(encoding="utf-8"))

    exit_code_2 = module.main()
    payload_2 = json.loads(primary_path.read_text(encoding="utf-8"))
    compat_2 = json.loads(compat_path.read_text(encoding="utf-8"))

    assert exit_code_1 == 0
    assert exit_code_2 == 0
    assert payload_1 == payload_2
    assert compat_1 == compat_2
    assert payload_1 == compat_1

    assert payload_1["suite"] == "pr1_tool_first"
    assert payload_1["schema_version"] == "1.1"
    assert payload_1["num_cases"] == payload_1["counts"]["num_cases"]
    assert payload_1["scored_cases"] == payload_1["counts"]["scored_cases"]
    assert payload_1["passed"] == payload_1["counts"]["passed"]
    assert isinstance(payload_1["pass_rate"], float)

    summary = payload_1["summary"]
    assert summary["counts"] == payload_1["counts"]
    metrics = summary["metrics"]
    for key in ("baseline_pass_rate", "tool_first_pass_rate", "pass_rate_delta"):
        assert isinstance(metrics[key], float)

    for section_name in ("math", "code", "overall"):
        section = payload_1[section_name]
        assert section["num_cases"] >= 0
        assert section["scored_cases"] >= 0
        assert section["passed"] >= 0
        assert isinstance(section["baseline_pass_rate"], float)
        assert isinstance(section["tool_first_pass_rate"], float)
        assert isinstance(section["pass_rate_delta"], float)
