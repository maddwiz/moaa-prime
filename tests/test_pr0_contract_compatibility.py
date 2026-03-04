from __future__ import annotations

from collections.abc import Mapping
import inspect
from numbers import Real
from pathlib import Path
from typing import Any

import pytest

from moaa_prime.agents.base import BaseAgent
from moaa_prime.core.app import MoAAPrime


RUN_ONCE_REQUIRED_KEYS = {"mode", "decision", "result", "oracle"}
DECISION_REQUIRED_KEYS = {
    "agent",
    "score",
    "reason",
    "rationale",
    "exploration_probability",
    "expected_utility",
    "selected_by_exploration",
    "components",
}
RESULT_REQUIRED_KEYS = {"agent", "text", "meta"}
ORACLE_REQUIRED_KEYS = {"score", "reason", "meta"}

SWARM_REQUIRED_KEYS = {
    "best",
    "candidates",
    "confidence",
    "trace",
    "mode",
    "avg_latency_proxy",
    "avg_cost_proxy",
    "learning_trace_path",
    "router_dataset_path",
}

CANDIDATE_REQUIRED_KEYS = {
    "agent",
    "text",
    "meta",
    "oracle",
    "round",
    "rank",
    "latency_proxy",
    "cost_proxy",
    "confidence_proxy",
}

TRACE_REQUIRED_KEYS = {"router", "swarm", "oracle", "final"}
ROUTER_TRACE_REQUIRED_KEYS = {"mode", "ranked", "exploration_probability"}
SWARM_TRACE_REQUIRED_KEYS = {"mode", "rounds", "top_k", "num_candidates", "cross_check", "pareto", "budget_mode"}
ORACLE_TRACE_REQUIRED_KEYS = {"mode", "scores"}
FINAL_TRACE_REQUIRED_KEYS = {"agent", "score", "confidence", "budget_mode"}
ROUTER_RANKED_REQUIRED_KEYS = {
    "agent",
    "score",
    "expected_utility",
    "exploration_probability",
    "selected_by_exploration",
    "reason",
    "rationale",
    "components",
}
ORACLE_SCORE_ENTRY_REQUIRED_KEYS = {"agent", "score", "reason", "components"}


def _assert_has_required_keys(payload: Mapping[str, Any], required: set[str]) -> None:
    missing = required.difference(payload.keys())
    assert not missing, f"Missing required keys: {sorted(missing)}"


def _assert_number(value: Any) -> None:
    assert isinstance(value, Real) and not isinstance(value, bool)


def _assert_oracle_payload(oracle: Mapping[str, Any]) -> None:
    _assert_has_required_keys(oracle, ORACLE_REQUIRED_KEYS)
    _assert_number(oracle["score"])
    assert isinstance(oracle["reason"], str)
    assert isinstance(oracle["meta"], Mapping)


def _assert_decision_payload(decision: Mapping[str, Any]) -> None:
    _assert_has_required_keys(decision, DECISION_REQUIRED_KEYS)
    assert isinstance(decision["agent"], str)
    _assert_number(decision["score"])
    assert isinstance(decision["reason"], str)
    assert isinstance(decision["rationale"], str)
    _assert_number(decision["exploration_probability"])
    _assert_number(decision["expected_utility"])
    assert isinstance(decision["selected_by_exploration"], bool)
    assert isinstance(decision["components"], Mapping)


def _assert_result_payload(result: Mapping[str, Any]) -> None:
    _assert_has_required_keys(result, RESULT_REQUIRED_KEYS)
    assert isinstance(result["agent"], str)
    assert isinstance(result["text"], str)
    assert isinstance(result["meta"], Mapping)

    memory = result["meta"].get("memory")
    assert isinstance(memory, Mapping)
    assert "local_hits" in memory
    assert "bank_hits" in memory
    assert type(memory["local_hits"]) is int
    assert type(memory["bank_hits"]) is int


def _assert_candidate_payload(candidate: Mapping[str, Any]) -> None:
    _assert_has_required_keys(candidate, CANDIDATE_REQUIRED_KEYS)
    assert isinstance(candidate["agent"], str)
    assert isinstance(candidate["text"], str)
    assert isinstance(candidate["meta"], Mapping)
    assert isinstance(candidate["round"], int)
    assert isinstance(candidate["rank"], int)
    _assert_number(candidate["latency_proxy"])
    _assert_number(candidate["cost_proxy"])
    _assert_number(candidate["confidence_proxy"])
    assert isinstance(candidate["oracle"], Mapping)
    _assert_oracle_payload(candidate["oracle"])


def _assert_trace_payload(trace: Mapping[str, Any]) -> None:
    _assert_has_required_keys(trace, TRACE_REQUIRED_KEYS)

    router = trace["router"]
    assert isinstance(router, Mapping)
    _assert_has_required_keys(router, ROUTER_TRACE_REQUIRED_KEYS)
    assert isinstance(router["mode"], str)
    assert isinstance(router["ranked"], list)
    _assert_number(router["exploration_probability"])
    if router["ranked"]:
        assert isinstance(router["ranked"][0], Mapping)
        _assert_has_required_keys(router["ranked"][0], ROUTER_RANKED_REQUIRED_KEYS)

    swarm = trace["swarm"]
    assert isinstance(swarm, Mapping)
    _assert_has_required_keys(swarm, SWARM_TRACE_REQUIRED_KEYS)
    assert isinstance(swarm["mode"], str)
    assert isinstance(swarm["rounds"], int)
    assert isinstance(swarm["top_k"], int)
    assert isinstance(swarm["num_candidates"], int)
    assert isinstance(swarm["cross_check"], Mapping)
    assert isinstance(swarm["pareto"], Mapping)
    assert isinstance(swarm["budget_mode"], str)

    oracle = trace["oracle"]
    assert isinstance(oracle, Mapping)
    _assert_has_required_keys(oracle, ORACLE_TRACE_REQUIRED_KEYS)
    assert isinstance(oracle["mode"], str)
    assert isinstance(oracle["scores"], list)
    if oracle["scores"]:
        assert isinstance(oracle["scores"][0], Mapping)
        _assert_has_required_keys(oracle["scores"][0], ORACLE_SCORE_ENTRY_REQUIRED_KEYS)

    final = trace["final"]
    assert isinstance(final, Mapping)
    _assert_has_required_keys(final, FINAL_TRACE_REQUIRED_KEYS)
    assert isinstance(final["agent"], str)
    _assert_number(final["score"])
    _assert_number(final["confidence"])
    assert isinstance(final["budget_mode"], str)


def test_pr0_agent_interface_contract() -> None:
    handle_sig = inspect.signature(BaseAgent.handle)
    assert list(handle_sig.parameters.keys()) == ["self", "prompt", "task_id"]
    assert handle_sig.parameters["task_id"].default == "default"

    app = MoAAPrime(seed=5)
    result = app.math.handle("Solve 1 + 1", task_id="pr0-agent-interface")

    assert isinstance(result.agent_name, str)
    assert isinstance(result.text, str)
    assert isinstance(result.meta, Mapping)
    memory = result.meta.get("memory")
    assert isinstance(memory, Mapping)
    assert type(memory["local_hits"]) is int
    assert type(memory["bank_hits"]) is int


@pytest.mark.parametrize("mode", ["v1", "v2", "v3"])
def test_pr0_run_once_contract_compatibility(mode: str) -> None:
    app = MoAAPrime(seed=7)

    out = app.run_once(
        "Solve 2x + 3 = 7",
        task_id=f"pr0-run-once-{mode}",
        mode=mode,
    )

    assert isinstance(out, Mapping)
    _assert_has_required_keys(out, RUN_ONCE_REQUIRED_KEYS)
    assert out["mode"] == mode

    assert isinstance(out["decision"], Mapping)
    _assert_decision_payload(out["decision"])

    assert isinstance(out["result"], Mapping)
    _assert_result_payload(out["result"])

    assert isinstance(out["oracle"], Mapping)
    _assert_oracle_payload(out["oracle"])


@pytest.mark.parametrize("mode", ["v1", "v2", "v3"])
def test_pr0_run_swarm_contract_compatibility(mode: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    app = MoAAPrime(seed=13)

    out = app.run_swarm(
        "Solve 2x + 3 = 7",
        task_id=f"pr0-run-swarm-{mode}",
        rounds=1,
        top_k=2,
        mode=mode,
    )

    assert isinstance(out, Mapping)
    _assert_has_required_keys(out, SWARM_REQUIRED_KEYS)
    assert out["mode"] == mode

    assert isinstance(out["best"], Mapping)
    _assert_candidate_payload(out["best"])

    assert isinstance(out["candidates"], list)
    assert out["candidates"]
    for candidate in out["candidates"]:
        assert isinstance(candidate, Mapping)
        _assert_candidate_payload(candidate)

    _assert_number(out["confidence"])
    _assert_number(out["avg_latency_proxy"])
    _assert_number(out["avg_cost_proxy"])

    assert isinstance(out["trace"], Mapping)
    _assert_trace_payload(out["trace"])

    assert isinstance(out["learning_trace_path"], str)
    assert isinstance(out["router_dataset_path"], str)
    assert Path(out["learning_trace_path"]).exists()
    assert Path(out["router_dataset_path"]).exists()
