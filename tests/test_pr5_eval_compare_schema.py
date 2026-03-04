from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _load_eval_compare_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "eval_compare.py"
    spec = importlib.util.spec_from_file_location("eval_compare_script", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_pr5_eval_compare_schema_is_stable_and_non_null(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    module = _load_eval_compare_module()

    exit_code_1 = module.main()
    report_path = tmp_path / "reports" / "eval_compare.json"
    payload_1 = json.loads(report_path.read_text(encoding="utf-8"))

    exit_code_2 = module.main()
    payload_2 = json.loads(report_path.read_text(encoding="utf-8"))

    assert exit_code_1 == 0
    assert exit_code_2 == 0
    assert payload_1 == payload_2

    assert payload_1["suite"] == "eval_compare"
    assert payload_1["schema_version"] == "1.1"
    assert payload_1["num_cases"] == payload_1["counts"]["num_cases"]
    assert payload_1["scored_cases"] == payload_1["counts"]["scored_cases"]
    assert payload_1["passed"] == payload_1["counts"]["passed"]
    assert isinstance(payload_1["pass_rate"], float)

    summary = payload_1["summary"]
    assert summary["counts"] == payload_1["counts"]
    metrics = summary["metrics"]
    for key in (
        "avg_oracle_score_v1",
        "avg_oracle_score_v2",
        "avg_oracle_score_delta",
        "win_rate_v2_over_v1",
        "routing_entropy_v1",
        "routing_entropy_v2",
        "routing_entropy_delta",
        "avg_cost_proxy_v1",
        "avg_cost_proxy_v2",
        "avg_cost_proxy_delta",
        "avg_latency_proxy_v1",
        "avg_latency_proxy_v2",
        "avg_latency_proxy_delta",
    ):
        assert isinstance(metrics[key], float)

    assert isinstance(payload_1["cases"], list)
    assert payload_1["cases"]
    assert isinstance(payload_1["trace_paths"], list)
