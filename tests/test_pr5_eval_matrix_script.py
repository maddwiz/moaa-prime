from __future__ import annotations

import importlib.util
import json
from collections import Counter
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
    assert "deterministic_checks" in run
    assert "summary" in run
    assert "cases" in run

    _assert_count_triplet(run)

    assert isinstance(run["cases"], list)
    assert run["cases"]
    for row in run["cases"]:
        assert "category" in row
        assert isinstance(row["category"], str)
        assert row["category"]


def _assert_count_triplet(block: dict, *, counts_key: str | None = "counts") -> None:
    assert "num_cases" in block
    assert "scored_cases" in block
    assert "passed" in block
    num_cases = int(block["num_cases"])
    scored_cases = int(block["scored_cases"])
    passed = int(block["passed"])
    assert num_cases >= scored_cases >= passed >= 0

    if counts_key and counts_key in block:
        counts = block[counts_key]
        assert isinstance(counts, dict)
        assert int(counts["num_cases"]) == num_cases
        assert int(counts["scored_cases"]) == scored_cases
        assert int(counts["passed"]) == passed


def test_pr5_eval_matrix_script_emits_deterministic_schema_and_required_deltas(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("MOAA_PR5_MATRIX_MIN_CORE_CASES", "72")
    monkeypatch.setenv("MOAA_PR5_MATRIX_MIN_TOOL_CASES", "12")
    monkeypatch.chdir(tmp_path)
    module = _load_eval_matrix_module()
    expected_core_cases = module._expanded_core_cases(min_cases=72)

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
    _assert_count_triplet(payload_1)
    assert isinstance(payload_1["pass_rate"], float)
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
        for category_block in run["category_summary"].values():
            _assert_count_triplet(category_block, counts_key=None)
        for deterministic_block in run["deterministic_checks"].values():
            _assert_count_triplet(deterministic_block, counts_key=None)

    assert REQUIRED_CONFIG_IDS.issubset(set(matrix["config_ids"]))
    expected_case_count = len(expected_core_cases)
    expected_category_counts = Counter(str(case["category"]) for case in expected_core_cases)
    expected_routing_cases = int(expected_category_counts["routing_intent"])
    expected_memory_cases = int(expected_category_counts["memory_behavior"])
    assert run_index["baseline_single"]["num_cases"] == expected_case_count
    assert run_index["swarm"]["num_cases"] == expected_case_count
    assert run_index["dual_gated"]["num_cases"] == expected_case_count
    for config_id in ("baseline_single", "swarm", "dual_gated"):
        observed = {
            category: int(block.get("num_cases", 0))
            for category, block in run_index[config_id]["category_summary"].items()
            if int(block.get("num_cases", 0)) > 0
        }
        assert observed == dict(expected_category_counts)
    assert run_index["swarm"]["avg_latency_proxy"] < 50.0
    assert run_index["dual_gated"]["avg_latency_proxy"] < 50.0
    assert run_index["swarm"]["pass_rate"] >= run_index["baseline_single"]["pass_rate"]
    assert run_index["dual_gated"]["pass_rate"] >= run_index["swarm"]["pass_rate"]
    assert run_index["swarm"]["deterministic_checks"]["routing_intent"]["num_cases"] == expected_routing_cases
    assert run_index["dual_gated"]["deterministic_checks"]["routing_intent"]["num_cases"] == expected_routing_cases
    assert run_index["swarm"]["deterministic_checks"]["memory_behavior"]["num_cases"] == expected_memory_cases
    assert run_index["dual_gated"]["deterministic_checks"]["memory_behavior"]["num_cases"] == expected_memory_cases
    dual_trigger_flags = [bool(row.get("dual_triggered", False)) for row in run_index["dual_gated"]["cases"]]
    assert not all(dual_trigger_flags)

    summary = payload_1["summary"]
    assert summary["counts"]["num_runs"] == len(matrix["runs"])
    for key in ("baseline_single", "swarm", "dual_gated", "tool_first", "memory", "sfc"):
        block = summary[key]
        _assert_count_triplet(block, counts_key=None)
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
    memory_deltas = [
        int(row.get("pass_delta", 0))
        for row in per_case["memory_on_vs_off"]
        if str(row.get("category", "")) == "memory_behavior"
    ]
    assert memory_deltas
    assert any(delta > 0 for delta in memory_deltas)

    assert compat_tool_1["suite"] == "pr1_tool_first"
    assert compat_tool_1["schema_version"] == "1.1"
    _assert_count_triplet(compat_tool_1)
    assert isinstance(compat_tool_1["pass_rate"], float)
    assert compat_tool_1["summary"]["counts"] == compat_tool_1["counts"]
    _assert_count_triplet(compat_tool_1["overall"], counts_key=None)
    _assert_count_triplet(compat_tool_1["math"], counts_key=None)
    _assert_count_triplet(compat_tool_1["code"], counts_key=None)
    assert compat_tool_1["overall"]["num_cases"] >= compat_tool_1["overall"]["passed"] >= 0
    assert compat_tool_1["overall"]["scored_cases"] == compat_tool_1["overall"]["num_cases"]


def test_pr5_eval_matrix_default_expansion_meets_longeval_volume() -> None:
    module = _load_eval_matrix_module()
    core_cases = module._expanded_core_cases(min_cases=module.DEFAULT_CORE_MIN_CASES)
    math_cases, code_cases = module._expanded_tool_first_cases(min_cases=module.DEFAULT_TOOL_FIRST_MIN_CASES)

    assert len(core_cases) >= 150
    category_counts = Counter(str(case["category"]) for case in core_cases)
    assert REQUIRED_CATEGORIES.issubset(set(category_counts))
    assert max(category_counts.values()) - min(category_counts.values()) <= 1

    tool_total = len(math_cases) + len(code_cases)
    assert tool_total >= module.DEFAULT_TOOL_FIRST_MIN_CASES

    matrix_total = (len(module.CORE_CONFIGS) * len(core_cases)) + (2 * tool_total)
    assert matrix_total >= 1200
