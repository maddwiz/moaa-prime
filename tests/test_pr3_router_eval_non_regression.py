from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys


def _load_eval_router_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "eval_router.py"
    spec = importlib.util.spec_from_file_location("eval_router_script", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_pr3_eval_router_reports_v3_non_regression_vs_v2(tmp_path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    report_path = tmp_path / "eval_router.json"

    result = subprocess.run(
        [sys.executable, str(repo_root / "scripts" / "eval_router.py")],
        cwd=repo_root,
        env={
            **os.environ,
            "MOAA_ROUTER_V3_MODEL": str(repo_root / "models" / "router_v3.pt"),
            "MOAA_ROUTER_EVAL_CASES_PATH": str(repo_root / "demos" / "demo_cases.json"),
            "MOAA_ROUTER_EVAL_REPORT_PATH": str(report_path),
        },
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"stdout={result.stdout}\nstderr={result.stderr}"
    assert "non_regression_vs_v2:" in result.stdout

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["suite"] == "eval_router"
    assert report["schema_version"] == "1.1"
    assert report["num_cases"] == report["counts"]["num_cases"]
    assert report["scored_cases"] == report["counts"]["scored_cases"]
    assert report["passed"] == report["counts"]["passed"]
    assert isinstance(report["pass_rate"], float)
    assert report["summary"]["counts"] == report["counts"]
    assert isinstance(report["summary"]["metrics"]["routing_accuracy_delta"], float)
    assert isinstance(report["summary"]["metrics"]["oracle_score_gain_delta"], float)

    routing_accuracy = report["routing_accuracy"]
    oracle_score_gain = report["oracle_score_gain"]
    assert float(routing_accuracy["v3"]) >= float(routing_accuracy["v2"])
    assert float(oracle_score_gain["v3"]) >= float(oracle_score_gain["v2"])

    non_regression = report["non_regression_vs_v2"]
    assert non_regression["routing_accuracy"]["passed"] is True
    assert non_regression["oracle_score_gain"]["passed"] is True
    assert non_regression["passed"] is True


def test_pr3_eval_router_default_expansion_meets_longeval_volume(monkeypatch) -> None:
    module = _load_eval_router_module()
    repo_root = Path(__file__).resolve().parents[1]
    monkeypatch.chdir(repo_root)
    monkeypatch.delenv("MOAA_ROUTER_EVAL_CASES_PATH", raising=False)

    base_cases = module._load_cases()
    expanded_1 = module._expand_eval_cases(base_cases, min_cases=module.DEFAULT_MIN_CASES)
    expanded_2 = module._expand_eval_cases(base_cases, min_cases=module.DEFAULT_MIN_CASES)

    assert len(expanded_1) >= 50
    assert [case.case_id for case in expanded_1] == [case.case_id for case in expanded_2]
    assert len({case.case_id for case in expanded_1}) == len(expanded_1)
