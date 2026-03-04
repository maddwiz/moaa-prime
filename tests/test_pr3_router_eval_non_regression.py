from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys


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
