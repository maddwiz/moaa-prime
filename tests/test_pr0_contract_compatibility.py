from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
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
ROUTE_TRACE_REQUIRED_KEYS = {"intent", "matched_features", "chosen_agent"}
ROUTER_INTENT_METADATA_OPTIONAL_KEYS = {
    "intent",
    "intent_scores",
    "intent_confidence",
    "matched_features",
    "chosen_agent",
    "alternatives",
    "ranking_rationale",
}

RUN_ONCE_REQUIRED_POSITIONAL_PARAMS = [
    ("prompt", inspect.Parameter.empty),
    ("task_id", "default"),
]
RUN_SWARM_REQUIRED_POSITIONAL_PARAMS = [
    ("prompt", inspect.Parameter.empty),
    ("task_id", "default"),
    ("rounds", 3),
    ("top_k", 2),
]


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


def _assert_router_ranked_entry_payload(entry: Mapping[str, Any]) -> None:
    _assert_has_required_keys(entry, ROUTER_RANKED_REQUIRED_KEYS)
    assert isinstance(entry["agent"], str)
    _assert_number(entry["score"])
    _assert_number(entry["expected_utility"])
    _assert_number(entry["exploration_probability"])
    assert isinstance(entry["selected_by_exploration"], bool)
    assert isinstance(entry["reason"], str)
    assert isinstance(entry["rationale"], str)
    assert isinstance(entry["components"], Mapping)


def _assert_oracle_score_entry_payload(entry: Mapping[str, Any]) -> None:
    _assert_has_required_keys(entry, ORACLE_SCORE_ENTRY_REQUIRED_KEYS)
    assert isinstance(entry["agent"], str)
    _assert_number(entry["score"])
    assert isinstance(entry["reason"], str)
    assert isinstance(entry["components"], Mapping)


def _assert_route_trace_payload(route_trace: Mapping[str, Any], *, decision_agent: str) -> None:
    _assert_has_required_keys(route_trace, ROUTE_TRACE_REQUIRED_KEYS)
    assert isinstance(route_trace["intent"], str)
    assert isinstance(route_trace["matched_features"], list)
    for feature in route_trace["matched_features"]:
        assert isinstance(feature, str)
    assert isinstance(route_trace["chosen_agent"], str)
    assert route_trace["chosen_agent"] == decision_agent

    if "intent_scores" in route_trace:
        assert isinstance(route_trace["intent_scores"], Mapping)
        for intent_name, score in route_trace["intent_scores"].items():
            assert isinstance(intent_name, str)
            _assert_number(score)
    if "intent_confidence" in route_trace:
        _assert_number(route_trace["intent_confidence"])
    if "ranking_rationale" in route_trace:
        assert isinstance(route_trace["ranking_rationale"], str)
    if "selected_by_exploration" in route_trace:
        assert isinstance(route_trace["selected_by_exploration"], bool)


def _assert_method_signature_compatibility(
    signature: inspect.Signature,
    required_positional_params: list[tuple[str, Any]],
) -> None:
    params = list(signature.parameters.values())
    assert params
    assert params[0].name == "self"

    required_end = 1 + len(required_positional_params)
    assert len(params) >= required_end

    for idx, (expected_name, expected_default) in enumerate(required_positional_params, start=1):
        param = params[idx]
        assert param.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
        assert param.name == expected_name
        if expected_default is inspect.Parameter.empty:
            assert param.default is inspect.Parameter.empty
        else:
            assert param.default == expected_default

    for param in params[required_end:]:
        assert param.kind in {inspect.Parameter.KEYWORD_ONLY, inspect.Parameter.VAR_KEYWORD}


def _assert_trace_payload(trace: Mapping[str, Any]) -> None:
    _assert_has_required_keys(trace, TRACE_REQUIRED_KEYS)

    router = trace["router"]
    assert isinstance(router, Mapping)
    _assert_has_required_keys(router, ROUTER_TRACE_REQUIRED_KEYS)
    assert isinstance(router["mode"], str)
    assert isinstance(router["ranked"], list)
    _assert_number(router["exploration_probability"])
    for ranked_entry in router["ranked"]:
        assert isinstance(ranked_entry, Mapping)
        _assert_router_ranked_entry_payload(ranked_entry)

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
    for score_entry in oracle["scores"]:
        assert isinstance(score_entry, Mapping)
        _assert_oracle_score_entry_payload(score_entry)

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


def test_pr0_run_once_signature_contract_compatibility() -> None:
    run_once_sig = inspect.signature(MoAAPrime.run_once)
    _assert_method_signature_compatibility(run_once_sig, RUN_ONCE_REQUIRED_POSITIONAL_PARAMS)


def test_pr0_run_swarm_signature_contract_compatibility() -> None:
    run_swarm_sig = inspect.signature(MoAAPrime.run_swarm)
    _assert_method_signature_compatibility(run_swarm_sig, RUN_SWARM_REQUIRED_POSITIONAL_PARAMS)


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

    route_trace = out.get("route_trace")
    if route_trace is not None:
        assert isinstance(route_trace, Mapping)
        _assert_route_trace_payload(route_trace, decision_agent=out["decision"]["agent"])


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
    assert "trace_path" not in out


def test_pr0_run_swarm_trace_path_conditional_field(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    app = MoAAPrime(seed=31)

    without_run_id = app.run_swarm(
        "Solve 2x + 3 = 7",
        task_id="pr0-run-swarm-trace-path-without-id",
        rounds=1,
        top_k=2,
        mode="v3",
    )
    assert "trace_path" not in without_run_id

    with_run_id = app.run_swarm(
        "Solve 2x + 3 = 7",
        task_id="pr0-run-swarm-trace-path-with-id",
        rounds=1,
        top_k=2,
        mode="v3",
        run_id="pr0-trace-path",
    )
    assert isinstance(with_run_id.get("trace_path"), str)
    assert Path(with_run_id["trace_path"]).exists()


def test_pr0_additive_optional_field_removal_policy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    app = MoAAPrime(seed=37)

    run_once_out = app.run_once(
        "Solve 2x + 3 = 7",
        task_id="pr0-additive-run-once",
        mode="v3",
    )
    run_once_required_only = dict(run_once_out)
    run_once_required_only.pop("route_trace", None)

    _assert_has_required_keys(run_once_required_only, RUN_ONCE_REQUIRED_KEYS)
    assert isinstance(run_once_required_only["decision"], Mapping)
    _assert_decision_payload(run_once_required_only["decision"])
    assert isinstance(run_once_required_only["result"], Mapping)
    _assert_result_payload(run_once_required_only["result"])
    assert isinstance(run_once_required_only["oracle"], Mapping)
    _assert_oracle_payload(run_once_required_only["oracle"])

    run_swarm_out = app.run_swarm(
        "Solve 2x + 3 = 7",
        task_id="pr0-additive-run-swarm",
        rounds=1,
        top_k=2,
        mode="v3",
        cross_check=True,
    )
    run_swarm_required_only = deepcopy(run_swarm_out)

    trace = run_swarm_required_only.get("trace")
    assert isinstance(trace, dict)
    router_trace = trace.get("router")
    assert isinstance(router_trace, dict)
    for key in ROUTER_INTENT_METADATA_OPTIONAL_KEYS:
        router_trace.pop(key, None)

    swarm_trace = trace.get("swarm")
    assert isinstance(swarm_trace, dict)
    swarm_trace.pop("dual_gate", None)

    candidates = run_swarm_required_only.get("candidates")
    assert isinstance(candidates, list)
    for candidate in candidates:
        if isinstance(candidate, dict):
            candidate.pop("critique", None)

    best = run_swarm_required_only.get("best")
    if isinstance(best, dict):
        best.pop("critique", None)

    _assert_has_required_keys(run_swarm_required_only, SWARM_REQUIRED_KEYS)
    assert isinstance(run_swarm_required_only["best"], Mapping)
    _assert_candidate_payload(run_swarm_required_only["best"])

    assert isinstance(run_swarm_required_only["candidates"], list)
    assert run_swarm_required_only["candidates"]
    for candidate in run_swarm_required_only["candidates"]:
        assert isinstance(candidate, Mapping)
        _assert_candidate_payload(candidate)

    _assert_number(run_swarm_required_only["confidence"])
    _assert_number(run_swarm_required_only["avg_latency_proxy"])
    _assert_number(run_swarm_required_only["avg_cost_proxy"])

    assert isinstance(run_swarm_required_only["trace"], Mapping)
    _assert_trace_payload(run_swarm_required_only["trace"])
