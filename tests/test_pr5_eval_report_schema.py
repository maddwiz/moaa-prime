from __future__ import annotations

import json
import math

from moaa_prime.eval.report import write_json_report
from moaa_prime.eval.runner import EvalResult


def test_pr5_eval_report_schema_has_stable_summary_and_non_null_numeric_fields(tmp_path) -> None:
    out_path = tmp_path / "reports" / "eval_report.json"
    results = [
        EvalResult(
            case_id="case_1",
            mode="once",
            output={"result": {"text": "ok"}},
            oracle_score=0.9,
            routing_entropy=0.4,
            cost_proxy=10.0,
            latency_proxy=40.0,
        ),
        EvalResult(
            case_id="case_2",
            mode="swarm",
            output={"best": {"oracle": {"score": 0.2}}},
            oracle_score=float("nan"),
            routing_entropy=float("inf"),
            cost_proxy=float("-inf"),
            latency_proxy=float("nan"),
        ),
    ]

    write_json_report(results, str(out_path), pass_threshold=0.75)
    payload = json.loads(out_path.read_text(encoding="utf-8"))

    assert payload["schema_version"] == "1.1"
    assert payload["num_cases"] == 2
    assert payload["scored_cases"] == 2
    assert payload["passed"] == 1

    counts = payload["summary"]["counts"]
    metrics = payload["summary"]["metrics"]

    assert counts["num_cases"] == 2
    assert counts["scored_cases"] == 2
    assert counts["passed"] == 1
    assert metrics["pass_threshold"] == 0.75

    for key in (
        "pass_rate",
        "avg_oracle_score",
        "avg_routing_entropy",
        "avg_cost_proxy",
        "avg_latency_proxy",
    ):
        assert isinstance(metrics[key], float)
        assert math.isfinite(metrics[key])
        assert isinstance(payload[key], float)
        assert math.isfinite(payload[key])
        assert payload[key] == metrics[key]

    assert isinstance(payload["results"], list)
    assert len(payload["results"]) == 2
