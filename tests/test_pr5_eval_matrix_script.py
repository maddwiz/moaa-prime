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
    assert "num_cases" in run
    assert "pass_rate" in run
    assert "avg_latency_proxy" in run
    assert "tool_verification_rate" in run
    assert "avg_oracle_score" in run
    assert "oracle_distribution" in run
    assert "cases" in run

    assert isinstance(run["cases"], list)
    assert run["cases"]


def test_pr5_eval_matrix_script_emits_deterministic_schema_and_required_deltas(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    module = _load_eval_matrix_module()

    exit_code_1 = module.main()
    report_path = tmp_path / "reports" / "eval_matrix.json"
    payload_1 = json.loads(report_path.read_text(encoding="utf-8"))

    exit_code_2 = module.main()
    payload_2 = json.loads(report_path.read_text(encoding="utf-8"))

    assert exit_code_1 == 0
    assert exit_code_2 == 0
    assert payload_1 == payload_2

    assert payload_1["suite"] == "pr5_eval_matrix"
    assert payload_1["schema_version"] == "1.0"

    matrix = payload_1["matrix"]
    assert isinstance(matrix["runs"], list)
    assert matrix["runs"]

    for run in matrix["runs"]:
        _assert_run_shape(run)

    assert REQUIRED_CONFIG_IDS.issubset(set(matrix["config_ids"]))

    summary = payload_1["summary"]
    assert summary["tool_first"]["pass_rate_delta_vs_baseline"] > 0.0
    assert summary["swarm"]["pass_rate_delta_vs_baseline"] > 0.0
    assert summary["dual_gated"]["pass_rate_delta_vs_baseline"] >= 0.0

    per_case = payload_1["per_case_diffs"]
    assert isinstance(per_case["swarm_vs_baseline_single"], list)
    assert isinstance(per_case["dual_gated_vs_baseline_single"], list)
    assert isinstance(per_case["tool_first_on_vs_off"], list)
    assert isinstance(per_case["memory_on_vs_off"], list)
    assert isinstance(per_case["sfc_on_vs_off"], list)

    assert per_case["swarm_vs_baseline_single"]
    assert per_case["dual_gated_vs_baseline_single"]
    assert per_case["tool_first_on_vs_off"]
