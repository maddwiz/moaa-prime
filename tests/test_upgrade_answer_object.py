from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from pathlib import Path

import pytest

from moaa_prime.core.app import MoAAPrime
from moaa_prime.eval.runner import EvalCase, EvalRunner
from moaa_prime.schema import ANSWER_OBJECT_KEYS, normalize_answer_object, upgrade_answer_object


def _assert_answer_object_shape(answer_object: Mapping[str, object]) -> None:
    assert set(answer_object.keys()) == set(ANSWER_OBJECT_KEYS)

    assert isinstance(answer_object["final"], str)

    assert isinstance(answer_object["tools"], list)
    for tool in answer_object["tools"]:
        assert isinstance(tool, str)

    assert isinstance(answer_object["confidence"], float)
    assert 0.0 <= answer_object["confidence"] <= 1.0

    assert isinstance(answer_object["notes"], list)
    for note in answer_object["notes"]:
        assert isinstance(note, str)

    assert isinstance(answer_object["trace"], Mapping)


def test_normalize_answer_object_run_once_shape() -> None:
    payload = {
        "mode": "v2",
        "decision": {"agent": "math-agent"},
        "route_trace": {
            "intent": "math",
            "matched_features": ["equation"],
            "chosen_agent": "math-agent",
            "ranking_rationale": "math selected by score",
        },
        "result": {
            "agent": "math-agent",
            "text": "x = 2",
            "meta": {
                "model": "tool_first:sympy",
                "tool_first": {"attempted": True, "solver": "sympy"},
            },
        },
        "oracle": {"score": 0.87, "reason": "oracle-check-ok", "meta": {}},
    }

    answer_object = normalize_answer_object(payload)
    _assert_answer_object_shape(answer_object)

    assert answer_object["final"] == "x = 2"
    assert answer_object["confidence"] == pytest.approx(0.87)
    assert "sympy" in answer_object["tools"]
    assert "oracle-check-ok" in answer_object["notes"]
    assert "router" in answer_object["trace"]


def test_normalize_answer_object_run_swarm_shape() -> None:
    payload = {
        "mode": "v3",
        "best": {
            "agent": "code-agent",
            "text": "def target(x):\n    return x + 1",
            "meta": {
                "model": "tool_first:python_verify",
                "tool_first": {
                    "attempted": True,
                    "verification": {"stage": "compile", "status": "pass", "passed": True},
                },
            },
            "oracle": {"score": 0.74, "reason": "compile-pass", "meta": {}},
            "round": 1,
            "rank": 0,
            "latency_proxy": 10.0,
            "cost_proxy": 2.0,
            "confidence_proxy": 0.71,
        },
        "candidates": [],
        "confidence": 0.68,
        "trace": {
            "router": {"mode": "v3", "ranked": [], "exploration_probability": 0.0},
            "swarm": {"mode": "v3", "rounds": 1, "top_k": 2, "num_candidates": 1, "cross_check": {}, "pareto": {}, "budget_mode": "balanced"},
            "oracle": {"mode": "oracle_v2", "scores": []},
            "final": {"agent": "code-agent", "score": 0.74, "confidence": 0.68, "budget_mode": "balanced"},
        },
    }

    answer_object = normalize_answer_object(payload)
    _assert_answer_object_shape(answer_object)

    assert answer_object["final"] == payload["best"]["text"]
    assert answer_object["confidence"] == pytest.approx(0.68)
    assert "exec" in answer_object["tools"]
    assert "compile-pass" in answer_object["notes"]
    assert answer_object["trace"] == payload["trace"]
    assert answer_object["trace"] is not payload["trace"]


def test_upgrade_answer_object_is_additive() -> None:
    payload = {
        "mode": "v1",
        "decision": {"agent": "math-agent"},
        "result": {"agent": "math-agent", "text": "4", "meta": {}},
        "oracle": {"score": 1.0, "reason": "exact", "meta": {}},
        "custom": {"keep": True},
    }
    before = deepcopy(payload)

    upgraded = upgrade_answer_object(payload)
    _assert_answer_object_shape(upgraded["answer_object"])

    for key, value in before.items():
        assert upgraded[key] == value

    upgraded_twice = upgrade_answer_object(upgraded)
    assert upgraded_twice["answer_object"] == upgraded["answer_object"]


def test_app_outputs_include_answer_object(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    app = MoAAPrime(seed=23)

    run_once_out = app.run_once("Solve 2x + 3 = 7", task_id="upgrade-once", mode="v3")
    assert {"mode", "decision", "result", "oracle"}.issubset(run_once_out.keys())
    _assert_answer_object_shape(run_once_out["answer_object"])
    assert run_once_out["answer_object"]["final"] == run_once_out["result"]["text"]

    run_swarm_out = app.run_swarm(
        "Solve 2x + 3 = 7",
        task_id="upgrade-swarm",
        rounds=1,
        top_k=2,
        mode="v3",
    )
    assert {"best", "candidates", "confidence", "trace", "mode"}.issubset(run_swarm_out.keys())
    _assert_answer_object_shape(run_swarm_out["answer_object"])
    assert run_swarm_out["answer_object"]["final"] == run_swarm_out["best"]["text"]


def test_eval_runner_upgrades_outputs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner = EvalRunner(model_mode="v3", seed=29)
    cases = [
        EvalCase(case_id="once", prompt="Solve 1+1", mode="once"),
        EvalCase(case_id="swarm", prompt="Solve 2+2", mode="swarm"),
    ]

    results = runner.run(cases)
    assert len(results) == 2
    for row in results:
        assert "answer_object" in row.output
        _assert_answer_object_shape(row.output["answer_object"])
