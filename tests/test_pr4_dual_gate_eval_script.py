from __future__ import annotations

import importlib.util
import json
from collections import Counter
from pathlib import Path

REQUIRED_CATEGORIES = {
    "math",
    "code",
    "reasoning",
    "safety",
    "routing_intent",
    "memory_behavior",
}


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


def _load_eval_dual_gate_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "eval_dual_gate.py"
    spec = importlib.util.spec_from_file_location("eval_dual_gate_script", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_pr4_eval_dual_gate_script_emits_deterministic_non_regression(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("MOAA_PR4_DUAL_EVAL_MIN_CASES", "60")
    monkeypatch.chdir(tmp_path)
    module = _load_eval_dual_gate_module()
    expected_cases = module._expanded_eval_cases(min_cases=60)

    exit_code_1 = module.main()
    report_path = tmp_path / "reports" / "dual_gated_eval.json"
    payload_1 = json.loads(report_path.read_text(encoding="utf-8"))

    exit_code_2 = module.main()
    payload_2 = json.loads(report_path.read_text(encoding="utf-8"))

    assert exit_code_1 == 0
    assert exit_code_2 == 0
    assert payload_1 == payload_2
    assert payload_1["suite"] == "pr4_dual_gate"
    assert payload_1["schema_version"] == "1.1"
    _assert_count_triplet(payload_1)
    assert isinstance(payload_1["pass_rate"], float)
    assert payload_1["num_cases"] == len(expected_cases)
    categories = {str(row.get("category", "")) for row in payload_1["cases"]}
    assert REQUIRED_CATEGORIES.issubset(categories)
    expected_counts = Counter(str(row["category"]) for row in expected_cases)
    observed_counts = Counter(str(row.get("category", "")) for row in payload_1["cases"])
    assert observed_counts == expected_counts

    baseline = payload_1["summary"]["baseline"]
    dual = payload_1["summary"]["dual_gated"]

    for block in (baseline, dual):
        _assert_count_triplet(block)
        assert block["num_cases"] == payload_1["num_cases"]
        assert block["scored_cases"] == payload_1["scored_cases"]
        assert block["num_cases"] >= 0
        assert block["scored_cases"] >= 0
        assert block["passed"] >= 0
        assert isinstance(block["pass_rate"], float)
        assert isinstance(block["mean_oracle_score"], float)

    assert isinstance(dual["pass_rate_delta_vs_baseline"], float)
    assert isinstance(dual["oracle_delta_vs_baseline"], float)
    assert isinstance(dual["trigger_rate"], float)
    assert 0.0 <= dual["trigger_rate"] < 1.0


def test_pr4_eval_dual_gate_default_expansion_meets_longeval_volume() -> None:
    module = _load_eval_dual_gate_module()
    expanded = module._expanded_eval_cases(min_cases=module.DEFAULT_MIN_CASES)
    category_counts = Counter(str(row["category"]) for row in expanded)

    assert len(expanded) >= 150
    assert REQUIRED_CATEGORIES.issubset(set(category_counts))
    assert max(category_counts.values()) - min(category_counts.values()) <= 1
