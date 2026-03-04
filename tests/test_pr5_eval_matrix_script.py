from __future__ import annotations

import importlib.util
import json
from pathlib import Path


REQUIRED_CONFIG_IDS = {
    "baseline_single",
    "swarm",
    "dual_gated",
    "tool_first_off",
    "tool_first_on",
    "memory_off",
    "memory_on",
    "sfc_off",
    "sfc_on",
}
REQUIRED_CATEGORIES = {
    "math",
    "code",
    "reasoning",
    "safety",
    "routing_intent",
    "memory_behavior",
}


def _load_eval_matrix_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "eval_matrix.py"
    spec = importlib.util.spec_from_file_location("eval_matrix_script", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _assert_run_shape(run: dict) -> None:
    assert "config_id" in run
    assert "suite" in run
    assert "strategy" in run
    assert "toggles" in run
    assert "counts" in run
    assert "num_cases" in run
    assert "scored_cases" in run
    assert "passed" in run
    assert "pass_rate" in run
    assert "avg_latency_proxy" in run
    assert "tool_verification_rate" in run
    assert "avg_oracle_score" in run
    assert "oracle_distribution" in run
    assert "category_summary" in run
    assert "summary" in run
    assert "cases" in run

    assert run["num_cases"] == run["counts"]["num_cases"]
    assert run["scored_cases"] == run["counts"]["scored_cases"]
    assert run["passed"] == run["counts"]["passed"]

    assert isinstance(run["cases"], list)
    assert run["cases"]
    for row in run["cases"]:
        assert "category" in row
        assert isinstance(row["category"], str)
        assert row["category"]


def test_pr5_eval_matrix_script_emits_deterministic_schema_and_required_deltas(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    module = _load_eval_matrix_module()

    exit_code_1 = module.main()
    report_path = tmp_path / "reports" / "eval_matrix.json"
    payload_1 = json.loads(report_path.read_text(encoding="utf-8"))
    compat_tool_path = tmp_path / "reports" / "eval_tool_first.json"
    compat_tool_1 = json.loads(compat_tool_path.read_text(encoding="utf-8"))

    exit_code_2 = module.main()
    payload_2 = json.loads(report_path.read_text(encoding="utf-8"))
    compat_tool_2 = json.loads(compat_tool_path.read_text(encoding="utf-8"))

    assert exit_code_1 == 0
    assert exit_code_2 == 0
    assert payload_1 == payload_2
    assert compat_tool_1 == compat_tool_2

    assert payload_1["suite"] == "pr5_eval_matrix"
    assert payload_1["schema_version"] == "1.1"
    assert payload_1["counts"]["num_runs"] == len(payload_1["matrix"]["runs"])
    assert payload_1["counts"]["num_cases"] >= payload_1["counts"]["scored_cases"] >= payload_1["counts"]["passed"] >= 0
    assert set(payload_1["categories"]["required"]) == REQUIRED_CATEGORIES
    assert REQUIRED_CATEGORIES.issubset(set(payload_1["categories"]["covered"]))
    assert payload_1["categories"]["missing"] == []

    matrix = payload_1["matrix"]
    assert isinstance(matrix["runs"], list)
    assert matrix["runs"]
    run_index = {run["config_id"]: run for run in matrix["runs"]}

    for run in matrix["runs"]:
        _assert_run_shape(run)

    assert REQUIRED_CONFIG_IDS.issubset(set(matrix["config_ids"]))
    assert run_index["baseline_single"]["num_cases"] >= 12
    assert run_index["swarm"]["num_cases"] >= 12
    assert run_index["dual_gated"]["num_cases"] >= 12
    assert run_index["swarm"]["avg_latency_proxy"] < 61.3335
    assert run_index["dual_gated"]["avg_latency_proxy"] < 61.3335
    assert run_index["dual_gated"]["pass_rate"] >= run_index["swarm"]["pass_rate"]
    dual_trigger_flags = [bool(row.get("dual_triggered", False)) for row in run_index["dual_gated"]["cases"]]
    assert any(dual_trigger_flags)
    assert not all(dual_trigger_flags)

    summary = payload_1["summary"]
    assert summary["counts"]["num_runs"] == len(matrix["runs"])
    for key in ("baseline_single", "swarm", "dual_gated", "tool_first", "memory", "sfc"):
        block = summary[key]
        assert block["num_cases"] >= 0
        assert block["scored_cases"] >= 0
        assert block["passed"] >= 0
        assert isinstance(block["pass_rate"], float)
        assert isinstance(block["avg_oracle_score"], float)
        assert isinstance(block["avg_latency_proxy"], float)
        assert isinstance(block["tool_verification_rate"], float)
        assert isinstance(block["pass_rate_delta_vs_baseline"], float)
        assert isinstance(block["oracle_delta_vs_baseline"], float)
        assert isinstance(block["latency_delta_vs_baseline"], float)
        assert isinstance(block["tool_verification_rate_delta_vs_baseline"], float)

    per_case = payload_1["per_case_diffs"]
    assert isinstance(per_case["swarm_vs_baseline_single"], list)
    assert isinstance(per_case["dual_gated_vs_baseline_single"], list)
    assert isinstance(per_case["tool_first_on_vs_off"], list)
    assert isinstance(per_case["memory_on_vs_off"], list)
    assert isinstance(per_case["sfc_on_vs_off"], list)

    assert per_case["swarm_vs_baseline_single"]
    assert per_case["dual_gated_vs_baseline_single"]
    assert per_case["tool_first_on_vs_off"]
    assert "category" in per_case["swarm_vs_baseline_single"][0]

    assert compat_tool_1["suite"] == "pr1_tool_first"
    assert compat_tool_1["schema_version"] == "1.1"
    assert compat_tool_1["num_cases"] == compat_tool_1["counts"]["num_cases"]
    assert compat_tool_1["scored_cases"] == compat_tool_1["counts"]["scored_cases"]
    assert compat_tool_1["passed"] == compat_tool_1["counts"]["passed"]
    assert isinstance(compat_tool_1["pass_rate"], float)
    assert compat_tool_1["summary"]["counts"] == compat_tool_1["counts"]
    assert compat_tool_1["overall"]["num_cases"] >= compat_tool_1["overall"]["passed"] >= 0
    assert compat_tool_1["overall"]["scored_cases"] == compat_tool_1["overall"]["num_cases"]
