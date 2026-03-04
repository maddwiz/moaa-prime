from __future__ import annotations

from collections.abc import Mapping

from moaa_prime.contracts import Contract
from moaa_prime.core.app import MoAAPrime
from moaa_prime.router.intent import analyze_prompt_intent
from moaa_prime.router.router_v2 import RouterV2
from moaa_prime.router.router_v3 import RouterV3, RouterV3Model


class DummyAgent:
    def __init__(self, contract: Contract) -> None:
        self.contract = contract


def _test_agents() -> list[DummyAgent]:
    return [
        DummyAgent(
            Contract(
                name="math-agent",
                domains=["math"],
                competence=0.75,
                reliability=0.78,
                cost_prior=0.25,
                description="math specialist",
            )
        ),
        DummyAgent(
            Contract(
                name="code-agent",
                domains=["code"],
                competence=0.83,
                reliability=0.82,
                cost_prior=0.25,
                description="code specialist",
            )
        ),
    ]


def test_pr3_intent_classifier_is_deterministic_for_same_prompt() -> None:
    prompt = "My python function throws a traceback TypeError."
    first = analyze_prompt_intent(prompt)
    second = analyze_prompt_intent(prompt)
    assert first == second
    assert first.intent == "code"
    assert "traceback_signal" in first.matched_features
    assert any(f.startswith("code_kw:") for f in first.matched_features)


def test_pr3_router_v2_intent_first_routing_is_deterministic() -> None:
    router_a = RouterV2(_test_agents(), seed=41)
    router_b = RouterV2(_test_agents(), seed=41)

    math_agents_a, math_decisions_a = router_a.route_top_k("Solve 2x + 3 = 7", k=2)
    math_agents_b, math_decisions_b = router_b.route_top_k("Solve 2x + 3 = 7", k=2)
    code_agents_a, code_decisions_a = router_a.route_top_k("Fix this python traceback", k=2)
    code_agents_b, code_decisions_b = router_b.route_top_k("Fix this python traceback", k=2)

    assert math_agents_a[0].contract.name == "math-agent"
    assert code_agents_a[0].contract.name == "code-agent"
    assert [a.contract.name for a in math_agents_a] == [a.contract.name for a in math_agents_b]
    assert [a.contract.name for a in code_agents_a] == [a.contract.name for a in code_agents_b]
    assert math_decisions_a[0].intent == "math"
    assert code_decisions_a[0].intent == "code"
    assert math_decisions_a[0].matched_features == math_decisions_b[0].matched_features
    assert code_decisions_a[0].matched_features == code_decisions_b[0].matched_features


def test_pr3_router_v3_intent_first_routing_stabilizes_when_model_is_neutral() -> None:
    router = RouterV3(_test_agents(), seed=9, model_path="/tmp/nonexistent-router-v3-pr3.pt")
    router.model = RouterV3Model(
        feature_names=["similarity"],
        weights={"similarity": 0.0},
        bias=0.0,
        calibration_scale=1.0,
        calibration_bias=0.0,
        seed=9,
    )

    math_agents, math_decisions = router.route_top_k("Solve 2x + 3 = 7", k=2)
    code_agents, code_decisions = router.route_top_k("Fix this python traceback", k=2)

    assert math_agents[0].contract.name == "math-agent"
    assert code_agents[0].contract.name == "code-agent"
    assert math_decisions[0].intent == "math"
    assert code_decisions[0].intent == "code"
    assert math_decisions[0].components["expected_success_stabilized"] > math_decisions[0].components["expected_success"]
    assert code_decisions[0].components["expected_success_stabilized"] > code_decisions[0].components["expected_success"]


def test_pr3_run_swarm_trace_emits_intent_metadata_schema(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    app = MoAAPrime(seed=17, mode="v3")

    out = app.run_swarm(
        "My python function throws a traceback",
        task_id="pr3-trace",
        mode="v3",
        rounds=1,
        top_k=2,
    )

    router_trace = out["trace"]["router"]
    assert isinstance(router_trace["intent"], str)
    assert isinstance(router_trace["matched_features"], list)
    assert isinstance(router_trace["chosen_agent"], str)
    assert isinstance(router_trace["alternatives"], list)
    assert isinstance(router_trace["ranking_rationale"], str)
    assert isinstance(router_trace["intent_scores"], Mapping)
    assert isinstance(router_trace["intent_confidence"], float)
    assert router_trace["intent"] == "code"
    assert router_trace["chosen_agent"] == router_trace["ranked"][0]["agent"]

    if router_trace["alternatives"]:
        first_alt = router_trace["alternatives"][0]
        assert isinstance(first_alt, Mapping)
        assert {"agent", "score", "reason", "rationale"}.issubset(first_alt.keys())


def test_pr3_run_once_exposes_route_trace_debug_surface() -> None:
    app = MoAAPrime(seed=23, mode="v3")
    out = app.run_once("Solve 2x + 3 = 7", task_id="pr3-run-once", mode="v3")
    trace = out["route_trace"]
    assert trace["intent"] == "math"
    assert trace["chosen_agent"] == out["decision"]["agent"]
    assert isinstance(trace["matched_features"], list)
    assert isinstance(trace["intent_scores"], Mapping)
    assert isinstance(trace["ranking_rationale"], str)
