from __future__ import annotations

import importlib.util
import json
from pathlib import Path


FAILURE_CLASSES = (
    "ROUTING_MISS",
    "TOOL_PARSE_FAIL",
    "TOOL_EXEC_FAIL",
    "FORMAT_FAIL",
    "MEMORY_DRIFT",
    "DUAL_REGRESSION",
    "SWARM_LOOP",
)


def _load_dashboard_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "dashboard.py"
    spec = importlib.util.spec_from_file_location("dashboard_script", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _seed_reports(report_dir: Path) -> None:
    _write_json(
        report_dir / "eval_matrix.json",
        {
            "pass_threshold": 0.75,
            "summary": {
                "baseline_single": {
                    "pass_rate": 0.3,
                    "avg_oracle_score": 0.7,
                    "avg_latency_proxy": 40.0,
                    "tool_verification_rate": 0.6,
                },
                "swarm": {
                    "pass_rate_delta_vs_baseline": 0.2,
                    "oracle_delta_vs_baseline": 0.1,
                    "latency_delta_vs_baseline": 12.0,
                    "tool_verification_rate_delta_vs_baseline": -0.4,
                },
                "dual_gated": {
                    "pass_rate_delta_vs_baseline": 0.1,
                    "oracle_delta_vs_baseline": 0.05,
                    "latency_delta_vs_baseline": 10.0,
                    "tool_verification_rate_delta_vs_baseline": -0.3,
                },
                "tool_first": {
                    "pass_rate_delta_vs_baseline": 0.5,
                    "oracle_delta_vs_baseline": 0.4,
                    "latency_delta_vs_baseline": 4.0,
                    "tool_verification_rate_delta_vs_baseline": 1.0,
                },
                "memory": {
                    "pass_rate_delta_vs_baseline": 0.0,
                    "oracle_delta_vs_baseline": -0.1,
                    "latency_delta_vs_baseline": 0.0,
                    "tool_verification_rate_delta_vs_baseline": 0.0,
                },
                "sfc": {
                    "pass_rate_delta_vs_baseline": 0.0,
                    "oracle_delta_vs_baseline": 0.0,
                    "latency_delta_vs_baseline": 2.0,
                    "tool_verification_rate_delta_vs_baseline": 0.0,
                },
            },
            "per_case_diffs": {
                "swarm_vs_baseline_single": [
                    {
                        "case_id": "math",
                        "pass_baseline": True,
                        "pass_target": False,
                        "pass_delta": -1,
                        "latency_delta": 22.0,
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
                        "case_id": "code_exec_safe",
                        "pass_baseline": False,
                        "pass_target": True,
                        "pass_delta": 1,
                        "tool_verified_delta": 1,
                    },
                ],
                "memory_on_vs_off": [
                    {
                        "case_id": "memory_case",
                        "pass_delta": 0,
                        "oracle_score_delta": -0.2,
                    }
                ],
                "dual_gated_vs_baseline_single": [
                    {
                        "case_id": "dual_case",
                        "pass_delta": -1,
                    }
                ],
            },
        },
    )
    _write_json(
        report_dir / "tool_first_eval.json",
        {
            "overall": {
                "pass_rate_delta": 0.5,
            }
        },
    )
    _write_json(
        report_dir / "dual_gated_eval.json",
        {
            "summary": {
                "dual_gated": {
                    "pass_rate_delta_vs_baseline": 0.1,
                    "trigger_rate": 1.0,
                }
            }
        },
    )
    _write_json(
        report_dir / "eval_compare.json",
        {
            "avg_latency_proxy": {"delta": 5.0},
            "routing_entropy": {"delta": -0.2},
        },
    )
    _write_json(
        report_dir / "eval_report.json",
        {
            "results": [
                {
                    "output": {
                        "route_trace": {
                            "intent": "math",
                            "chosen_agent": "code-agent",
                        },
                        "result": {
                            "meta": {
                                "memory": {"local_hits": 0},
                                "tool_first": {
                                    "prompt_probe": {
                                        "verification": {
                                            "status": "fail",
                                            "error_type": "ExtractionError",
                                            "error_message": "no_python_source_found",
                                        }
                                    },
                                    "proposal_probe": {
                                        "verification": {
                                            "status": "fail",
                                            "error_type": "RuntimeError",
                                            "error_message": "exec timeout",
                                        }
                                    },
                                },
                            }
                        },
                    }
                }
            ]
        },
    )
    _write_json(
        report_dir / "eval_router.json",
        {
            "routing_accuracy": {"delta": -0.1},
            "oracle_score_gain": {"delta": 0.03},
            "latency_efficiency": {"delta": -1.0},
        },
    )
    _write_json(
        report_dir / "router_train_report.json",
        {
            "training_accuracy": 0.82,
            "training_brier_score": 0.12,
            "training_ece": 0.08,
        },
    )
    _write_json(report_dir / "final_report.json", {"verdict": "ready"})


def test_pr7_dashboard_renders_sections_and_taxonomy(tmp_path, capsys) -> None:
    reports_dir = tmp_path / "reports"
    _seed_reports(reports_dir)

    module = _load_dashboard_module()

    exit_code_1 = module.main(["--reports-dir", str(reports_dir)])
    out_1 = capsys.readouterr().out
    exit_code_2 = module.main(["--reports-dir", str(reports_dir)])
    out_2 = capsys.readouterr().out

    assert exit_code_1 == 0
    assert exit_code_2 == 0
    assert out_1 == out_2

    assert "MOAA-Prime Dashboard" in out_1
    assert "== Mode Deltas ==" in out_1
    assert "== Failure Taxonomy ==" in out_1
    assert "tool_first.pass_rate_delta=+0.5000" in out_1
    assert "dual_gate.pass_rate_delta=+0.1000" in out_1

    for failure_class in FAILURE_CLASSES:
        assert f"{failure_class}:" in out_1

    assert "ROUTING_MISS: 2" in out_1
    assert "TOOL_PARSE_FAIL: 2" in out_1
    assert "TOOL_EXEC_FAIL: 2" in out_1
    assert "MEMORY_DRIFT: 1" in out_1
    assert "DUAL_REGRESSION: 1" in out_1
    assert "SWARM_LOOP: 2" in out_1


def test_pr7_dashboard_missing_reports_is_non_fatal(tmp_path, capsys) -> None:
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    module = _load_dashboard_module()

    exit_code = module.main(["--reports-dir", str(reports_dir)])
    out = capsys.readouterr().out

    assert exit_code == 0
    assert "warnings: 8" in out
    assert "artifact.eval_matrix.status=missing" in out
    assert "artifact.final_report.status=missing" in out
    assert "pass_threshold=NA" in out
    assert "verdict=NA" in out

    for failure_class in FAILURE_CLASSES:
        assert f"{failure_class}: 0" in out
