from __future__ import annotations

from statistics import mean

import pytest

from moaa_prime.core.app import MoAAPrime
from moaa_prime.duality import (
    DualSelectionCandidate,
    GatedDualBrainSelector,
    select_gated_dual,
)


def test_pr4_trigger_logic_no_signal() -> None:
    selector = GatedDualBrainSelector(low_confidence_threshold=0.60, high_ambiguity_threshold=0.55)

    decision = selector.evaluate_trigger(confidence=0.91, ambiguity=0.20, tool_failed=False)

    assert decision.should_trigger is False
    assert decision.reasons == ()
    assert decision.tool_failed is False


def test_pr4_trigger_logic_combined_reason_order_is_deterministic() -> None:
    selector = GatedDualBrainSelector(low_confidence_threshold=0.60, high_ambiguity_threshold=0.55)

    decision = selector.evaluate_trigger(
        confidence=0.25,
        ambiguity=0.90,
        answer_metadata={"tool_first": {"attempted": True, "success": False}},
    )

    assert decision.should_trigger is True
    assert decision.reasons == ("low-confidence", "high-ambiguity", "tool-fail")


@pytest.mark.parametrize(
    "answer_metadata",
    [
        pytest.param({"tool_first": {"attempted": True, "success": False}}, id="tool-first-success-flag"),
        pytest.param({"tool_first": {"verification": {"status": "fail", "passed": False}}}, id="verification-fail"),
    ],
)
def test_pr4_trigger_logic_tool_fail_detection(answer_metadata: dict[str, object]) -> None:
    selector = GatedDualBrainSelector()

    decision = selector.evaluate_trigger(confidence=0.99, ambiguity=0.01, answer_metadata=answer_metadata)

    assert decision.should_trigger is True
    assert decision.tool_failed is True
    assert decision.reasons == ("tool-fail",)


def test_pr4_trigger_logic_ambiguity_from_ranked_scores_is_deterministic() -> None:
    selector = GatedDualBrainSelector(high_ambiguity_threshold=0.95)

    ambiguity_a = selector.ambiguity_from_scores([0.81, 0.80, 0.05])
    ambiguity_b = selector.ambiguity_from_scores([0.81, 0.80, 0.05])
    decision = selector.evaluate_trigger(confidence=0.95, ranked_scores=[0.81, 0.80, 0.05])

    assert ambiguity_a == ambiguity_b == pytest.approx(0.99)
    assert decision.should_trigger is True
    assert decision.reasons == ("high-ambiguity",)


def test_pr4_selector_prefers_tool_verified_candidate_before_oracle_score() -> None:
    selector = GatedDualBrainSelector()
    single = DualSelectionCandidate(label="single", text="Precise answer", oracle_score=0.93, tool_verified=False)
    dual = DualSelectionCandidate(label="dual", text="Tool-backed answer", oracle_score=0.71, tool_verified=True)

    winner, reason = selector.select_winner((single, dual))

    assert winner.label == "dual"
    assert reason == "tool-verified"


def test_pr4_selector_uses_higher_oracle_score_when_no_tool_verified() -> None:
    selector = GatedDualBrainSelector()
    single = DualSelectionCandidate(label="single", text="answer", oracle_score=0.62, tool_verified=False)
    dual = DualSelectionCandidate(label="dual", text="better answer", oracle_score=0.75, tool_verified=False)

    winner, reason = selector.select_winner((single, dual))

    assert winner.label == "dual"
    assert reason == "oracle-score"


def test_pr4_selector_uses_stable_shorter_cleaner_fallback_for_tie() -> None:
    selector = GatedDualBrainSelector()
    single = DualSelectionCandidate(label="single", text="Final answer: 42", oracle_score=0.80, tool_verified=False)
    dual = DualSelectionCandidate(
        label="dual",
        text="```python\n# TODO refine\nprint(42)\n```\n\n",
        oracle_score=0.80,
        tool_verified=False,
    )

    winner_a, reason_a = selector.select_winner((single, dual))
    winner_b, reason_b = selector.select_winner((single, dual))

    assert winner_a.label == "single"
    assert winner_b.label == "single"
    assert reason_a == reason_b == "fallback-shorter-cleaner"


def test_pr4_run_candidate_set_includes_single_and_dual_when_triggered() -> None:
    selector = GatedDualBrainSelector(low_confidence_threshold=0.60)
    single = {"label": "single", "text": "baseline", "oracle_score": 0.61}
    dual = {"label": "dual", "text": "dual-answer", "oracle_score": 0.78}

    result = selector.run(single=single, dual=dual, confidence=0.30, ambiguity=0.10)

    assert result.trigger.should_trigger is True
    assert [c.label for c in result.candidates] == ["single", "dual"]


def test_pr4_run_keeps_single_only_when_gate_not_triggered() -> None:
    selector = GatedDualBrainSelector(low_confidence_threshold=0.60, high_ambiguity_threshold=0.55)
    single = {"label": "single", "text": "baseline", "oracle_score": 0.70}
    dual = {"label": "dual", "text": "dual-answer", "oracle_score": 0.90}

    result = selector.run(single=single, dual=dual, confidence=0.95, ambiguity=0.10, tool_failed=False)

    assert result.trigger.should_trigger is False
    assert [c.label for c in result.candidates] == ["single"]
    assert result.winner.label == "single"


def test_pr4_regression_gated_dual_non_underperforming_vs_baseline_fixture_suite() -> None:
    selector = GatedDualBrainSelector(low_confidence_threshold=0.60, high_ambiguity_threshold=0.55)

    fixtures = [
        {
            "confidence": 0.93,
            "ambiguity": 0.12,
            "single": {"label": "single", "text": "short baseline", "oracle_score": 0.88, "tool_verified": False},
            "dual": {"label": "dual", "text": "dual alt", "oracle_score": 0.95, "tool_verified": False},
        },
        {
            "confidence": 0.35,
            "ambiguity": 0.20,
            "single": {"label": "single", "text": "baseline weak", "oracle_score": 0.55, "tool_verified": False},
            "dual": {"label": "dual", "text": "dual improved", "oracle_score": 0.80, "tool_verified": False},
        },
        {
            "confidence": 0.84,
            "ambiguity": 0.80,
            "single": {"label": "single", "text": "clean answer", "oracle_score": 0.76, "tool_verified": False},
            "dual": {"label": "dual", "text": "noisy answer...", "oracle_score": 0.76, "tool_verified": False},
        },
        {
            "confidence": 0.92,
            "ambiguity": 0.15,
            "single": {"label": "single", "text": "single higher score", "oracle_score": 0.74, "tool_verified": False},
            "dual": {"label": "dual", "text": "tool verified", "oracle_score": 0.62, "tool_verified": True},
            "answer_metadata": {"tool_first": {"attempted": True, "success": False}},
        },
        {
            "confidence": 0.58,
            "ambiguity": 0.51,
            "single": {"label": "single", "text": "single", "oracle_score": 0.68, "tool_verified": False},
            "dual": {"label": "dual", "text": "dual", "oracle_score": 0.72, "tool_verified": False},
        },
        {
            "confidence": 0.79,
            "ambiguity": 0.61,
            "single": {"label": "single", "text": "final answer: 10", "oracle_score": 0.60, "tool_verified": False},
            "dual": {
                "label": "dual",
                "text": "```python\n# placeholder\nprint(10)\n```",
                "oracle_score": 0.60,
                "tool_verified": False,
            },
        },
    ]

    def _run_once() -> tuple[list[str], float]:
        labels: list[str] = []
        scores: list[float] = []
        for fixture in fixtures:
            result = selector.run(
                single=fixture["single"],
                dual=fixture["dual"],
                confidence=fixture["confidence"],
                ambiguity=fixture["ambiguity"],
                answer_metadata=fixture.get("answer_metadata"),
            )
            labels.append(result.winner.label)
            scores.append(result.winner.oracle_score)
        return labels, mean(scores)

    baseline_mean = mean(float(f["single"]["oracle_score"]) for f in fixtures)
    first_labels, gated_mean_a = _run_once()
    second_labels, gated_mean_b = _run_once()

    assert first_labels == second_labels
    assert gated_mean_a == pytest.approx(gated_mean_b)
    assert first_labels == ["single", "dual", "single", "dual", "dual", "single"]
    assert gated_mean_a >= baseline_mean


def test_pr4_select_gated_dual_function_matches_class_behavior() -> None:
    selector = GatedDualBrainSelector(low_confidence_threshold=0.60)
    kwargs = {
        "single": {"label": "single", "text": "A", "oracle_score": 0.40},
        "dual": {"label": "dual", "text": "B", "oracle_score": 0.70},
        "confidence": 0.20,
        "ambiguity": 0.10,
    }

    class_result = selector.run(**kwargs)
    func_result = select_gated_dual(**kwargs, low_confidence_threshold=0.60, high_ambiguity_threshold=0.55)

    assert class_result.winner.label == func_result.winner.label
    assert class_result.winner.oracle_score == func_result.winner.oracle_score


def test_pr4_run_swarm_dual_gate_default_is_opt_out_and_contract_safe() -> None:
    app = MoAAPrime(seed=41, mode="v3")
    out = app.run_swarm("Solve 2x + 3 = 7", mode="v3", rounds=1, top_k=2)

    assert all(str(c.get("agent", "")) != "dual-brain" for c in out["candidates"])
    dual_gate = out["trace"]["swarm"]["dual_gate"]
    assert dual_gate["enabled"] is False
    assert dual_gate["triggered"] is False
    assert dual_gate["selector"]["rule"] == "disabled"


def test_pr4_run_swarm_dual_gate_triggered_includes_single_and_dual_candidates() -> None:
    app = MoAAPrime(seed=43, mode="v3")
    out = app.run_swarm(
        "Explain why 1/0 is undefined, then give a safe Python example.",
        mode="v3",
        rounds=1,
        top_k=2,
        dual_gate=True,
        dual_gate_config={"high_ambiguity_threshold": 0.0},
    )

    dual_gate = out["trace"]["swarm"]["dual_gate"]
    assert dual_gate["enabled"] is True
    assert dual_gate["triggered"] is True
    assert dual_gate["candidate_labels"] == ["single", "dual"]
    assert dual_gate["selector"]["winner_source"] in {"single", "dual"}
    assert dual_gate["selector"]["rule"] in {"tool-verified", "oracle-score", "fallback-shorter-cleaner"}
    assert any(str(c.get("agent", "")) == "dual-brain" for c in out["candidates"])


def test_pr4_run_swarm_dual_gate_non_regression_vs_single_baseline() -> None:
    prompts = [
        "Solve 2x + 3 = 7",
        "Write Python: function add(a,b) returns a+b",
        "Explain why 1/0 is undefined with a safe Python snippet",
        "Fix this traceback TypeError in my function",
    ]

    baseline_scores: list[float] = []
    gated_scores: list[float] = []

    for idx, prompt in enumerate(prompts):
        base_app = MoAAPrime(seed=73, mode="v3")
        gated_app = MoAAPrime(seed=73, mode="v3")

        baseline = base_app.run_swarm(prompt, task_id=f"pr4-base-{idx}", mode="v3", rounds=1, top_k=2, dual_gate=False)
        gated = gated_app.run_swarm(
            prompt,
            task_id=f"pr4-gated-{idx}",
            mode="v3",
            rounds=1,
            top_k=2,
            dual_gate=True,
            dual_gate_config={"high_ambiguity_threshold": 0.0},
        )

        baseline_scores.append(float((baseline["best"]["oracle"] or {}).get("score", 0.0)))
        gated_scores.append(float((gated["best"]["oracle"] or {}).get("score", 0.0)))

    assert mean(gated_scores) >= mean(baseline_scores)
