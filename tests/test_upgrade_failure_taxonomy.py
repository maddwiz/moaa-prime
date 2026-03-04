from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from moaa_prime.eval.failure_taxonomy import (
    FAILURE_CLASSES,
    REMEDIATION_BY_CLASS,
    build_remediation_plan,
    classify_tool_verification_failure,
    derive_failure_taxonomy,
    get_remediation_mapping,
    is_dual_regression,
    is_memory_drift,
    is_routing_miss,
    is_swarm_loop,
    remediation_for,
)


EXPECTED_FAILURE_CLASSES = (
    "ROUTING_MISS",
    "TOOL_PARSE_FAIL",
    "TOOL_EXEC_FAIL",
    "FORMAT_FAIL",
    "MEMORY_DRIFT",
    "DUAL_REGRESSION",
    "SWARM_LOOP",
)

EXPECTED_REMEDIATION = {
    "ROUTING_MISS": {
        "owner": "router",
        "priority": "high",
        "action": "Refresh intent calibration data and tighten router policy thresholds.",
        "metric": "routing_accuracy_delta",
        "playbook": "router_retrain",
    },
    "TOOL_PARSE_FAIL": {
        "owner": "tooling",
        "priority": "high",
        "action": "Harden code extraction and parser guards before tool execution.",
        "metric": "tool_verification_rate",
        "playbook": "tool_parser_hardening",
    },
    "TOOL_EXEC_FAIL": {
        "owner": "tooling",
        "priority": "high",
        "action": "Expand sandbox runtime checks and add execution fallback handling.",
        "metric": "tool_verification_rate",
        "playbook": "tool_runtime_guardrails",
    },
    "FORMAT_FAIL": {
        "owner": "policy",
        "priority": "medium",
        "action": "Strengthen output schema constraints and post-format normalization.",
        "metric": "pass_rate",
        "playbook": "response_format_enforcement",
    },
    "MEMORY_DRIFT": {
        "owner": "memory",
        "priority": "medium",
        "action": "Re-score memory retrieval quality and clamp low-signal memory injections.",
        "metric": "oracle_score_delta",
        "playbook": "memory_retrieval_audit",
    },
    "DUAL_REGRESSION": {
        "owner": "dual",
        "priority": "high",
        "action": "Re-tune dual-gate trigger policy against single-agent baseline regressions.",
        "metric": "dual_gate_pass_rate_delta",
        "playbook": "dual_gate_rebalance",
    },
    "SWARM_LOOP": {
        "owner": "swarm",
        "priority": "medium",
        "action": "Cap exploration loops when latency rises without pass-rate gain.",
        "metric": "latency_efficiency_delta",
        "playbook": "swarm_loop_clamp",
    },
}


def _load_dashboard_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "dashboard.py"
    spec = importlib.util.spec_from_file_location("dashboard_script", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_failure_classes_are_stable() -> None:
    assert FAILURE_CLASSES == EXPECTED_FAILURE_CLASSES


def test_classification_helpers_and_report_snippets() -> None:
    assert is_routing_miss(intent="math", chosen_agent="code-agent") is True
    assert is_routing_miss(intent="math", chosen_agent="math-agent") is False

    assert (
        classify_tool_verification_failure(
            status="fail",
            error_type="ExtractionError",
            error_message="no_python_source_found",
        )
        == "TOOL_PARSE_FAIL"
    )
    assert (
        classify_tool_verification_failure(
            status="fail",
            error_type="RuntimeError",
            error_message="exec timeout",
        )
        == "TOOL_EXEC_FAIL"
    )
    assert (
        classify_tool_verification_failure(
            status="fail",
            error_type="ContractError",
            error_message="json schema mismatch",
        )
        == "FORMAT_FAIL"
    )
    assert classify_tool_verification_failure(status="ok", error_type="", error_message="") is None

    assert is_memory_drift(pass_delta=0, oracle_delta=-0.01) is True
    assert is_memory_drift(local_hits=-1) is True
    assert is_dual_regression(pass_delta=-0.1) is True
    assert is_swarm_loop(latency_delta=1.0, pass_delta=0.0) is True
    assert is_swarm_loop(latency_delta=1.0, entropy_delta=-0.1) is True

    reports = {
        "eval_matrix": {
            "per_case_diffs": {
                "swarm_vs_baseline_single": [
                    {
                        "pass_baseline": True,
                        "pass_target": False,
                        "pass_delta": -1,
                        "latency_delta": 3.0,
                    }
                ],
                "tool_first_on_vs_off": [
                    {
                        "case_id": "code_missing_colon",
                        "pass_baseline": False,
                        "pass_target": True,
                        "pass_delta": 1,
                        "tool_verified_delta": 1,
                    },
                    {
                        "case_id": "runtime_traceback_case",
                        "pass_baseline": False,
                        "pass_target": True,
                        "pass_delta": 1,
                        "tool_verified_delta": 1,
                    },
                    {
                        "case_id": "format_regression",
                        "pass_baseline": True,
                        "pass_target": False,
                        "pass_delta": -1,
                        "tool_verified_delta": 0,
                    },
                ],
                "memory_on_vs_off": [{"pass_delta": 0, "oracle_score_delta": -0.2}],
                "dual_gated_vs_baseline_single": [{"pass_delta": -1}],
            }
        },
        "eval_report": {
            "results": [
                {
                    "output": {
                        "route_trace": {
                            "intent": "code",
                            "chosen_agent": "math-agent",
                        },
                        "result": {
                            "meta": {
                                "memory": {"local_hits": -1},
                                "tool_first": {
                                    "prompt_probe": {
                                        "verification": {
                                            "status": "fail",
                                            "error_type": "ExtractionError",
                                            "error_message": "parse failed to extract",
                                        }
                                    },
                                    "proposal_probe": {
                                        "verification": {
                                            "status": "fail",
                                            "error_type": "RuntimeError",
                                            "error_message": "runtime timeout",
                                        }
                                    },
                                },
                            }
                        },
                    }
                }
            ]
        },
        "dual_gated_eval": {
            "summary": {
                "dual_gated": {
                    "pass_rate_delta_vs_baseline": -0.05,
                }
            }
        },
        "eval_compare": {
            "avg_latency_proxy": {"delta": 4.0},
            "routing_entropy": {"delta": -0.2},
        },
    }

    counts = derive_failure_taxonomy(reports)

    assert counts == {
        "ROUTING_MISS": 2,
        "TOOL_PARSE_FAIL": 2,
        "TOOL_EXEC_FAIL": 2,
        "FORMAT_FAIL": 1,
        "MEMORY_DRIFT": 2,
        "DUAL_REGRESSION": 2,
        "SWARM_LOOP": 2,
    }


def test_remediation_mapping_is_stable_and_deterministic() -> None:
    assert tuple(REMEDIATION_BY_CLASS.keys()) == EXPECTED_FAILURE_CLASSES
    assert get_remediation_mapping() == EXPECTED_REMEDIATION
    assert remediation_for("ROUTING_MISS") == EXPECTED_REMEDIATION["ROUTING_MISS"]
    assert remediation_for("UNKNOWN") is None

    copied = get_remediation_mapping()
    copied["ROUTING_MISS"]["owner"] = "changed"
    assert REMEDIATION_BY_CLASS["ROUTING_MISS"]["owner"] == "router"

    plan = build_remediation_plan(
        {
            "ROUTING_MISS": 2,
            "TOOL_EXEC_FAIL": 2,
            "FORMAT_FAIL": 1,
        }
    )
    assert [row["failure_class"] for row in plan] == ["ROUTING_MISS", "TOOL_EXEC_FAIL", "FORMAT_FAIL"]
    assert [row["count"] for row in plan] == [2, 2, 1]
    assert plan[0]["playbook"] == EXPECTED_REMEDIATION["ROUTING_MISS"]["playbook"]
    assert build_remediation_plan({"ROUTING_MISS": 2}, top_k=1) == [plan[0]]
    assert build_remediation_plan({}) == []


def test_dashboard_integration_emits_expected_taxonomy_keys(tmp_path: Path) -> None:
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    # Keep a valid artifact present so integration path handles mixed report states.
    (reports_dir / "final_report.json").write_text(json.dumps({"verdict": "ok"}), encoding="utf-8")

    module = _load_dashboard_module()
    dashboard = module.build_dashboard(reports_dir)

    taxonomy = dashboard["failure_taxonomy"]
    counts = taxonomy["counts"]

    assert taxonomy["source"] == "derived_from_reports"
    assert list(counts.keys()) == list(EXPECTED_FAILURE_CLASSES)
    assert set(counts.keys()) == set(EXPECTED_FAILURE_CLASSES)
    assert all(value == 0 for value in counts.values())
    assert taxonomy["remediation"] == []
