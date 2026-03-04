from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Mapping

import pytest

from moaa_prime.core.app import MoAAPrime
from moaa_prime.swarm.manager import SwarmManager


def _candidate(
    *,
    agent: str,
    text: str,
    score: float,
    meta: Mapping[str, Any] | None = None,
    oracle_meta: Mapping[str, Any] | None = None,
    latency: float = 100.0,
    cost: float = 60.0,
    confidence: float | None = None,
) -> dict[str, Any]:
    return {
        "agent": str(agent),
        "text": str(text),
        "meta": dict(meta or {}),
        "oracle": {
            "score": float(score),
            "reason": "stub",
            "meta": dict(oracle_meta or {}),
        },
        "round": 1,
        "rank": 0,
        "latency_proxy": float(latency),
        "cost_proxy": float(cost),
        "confidence_proxy": float(score if confidence is None else confidence),
    }


class _FixedAgent:
    def __init__(self, *, name: str, text: str, meta: Mapping[str, Any], cost_prior: float = 0.3) -> None:
        self.name = str(name)
        self._text = str(text)
        self._meta = dict(meta)
        self.contract = SimpleNamespace(name=self.name, domains=["test"], cost_prior=float(cost_prior))

    def handle(self, prompt: str, task_id: str = "default"):
        _ = prompt
        _ = task_id
        return SimpleNamespace(agent_name=self.name, text=self._text, meta=dict(self._meta))


class _NoTaskIdAgent:
    def __init__(self) -> None:
        self.contract = SimpleNamespace(name="no-taskid-agent", domains=["test"], cost_prior=0.1)

    def handle(self, prompt: str):
        _ = prompt
        return SimpleNamespace(agent_name="no-taskid-agent", text="ok", meta={})


class _InternalTypeErrorAgent:
    def __init__(self) -> None:
        self.contract = SimpleNamespace(name="internal-typeerror-agent", domains=["test"], cost_prior=0.1)

    def handle(self, prompt: str, task_id: str = "default"):
        _ = (prompt, task_id)
        raise TypeError("internal type error from agent")


class _OracleByText:
    def __init__(self, scores: Mapping[str, float]) -> None:
        self._scores = {str(k): float(v) for k, v in scores.items()}

    def verdict(self, prompt: str, answer: str, *, answer_metadata: Mapping[str, Any] | None = None):
        _ = prompt
        text = str(answer or "")
        score = float(self._scores.get(text, 0.5))

        verification = {}
        tool_meta = (answer_metadata or {}).get("tool_first") if isinstance(answer_metadata, Mapping) else None
        if isinstance(tool_meta, Mapping):
            signal = tool_meta.get("verification")
            if isinstance(signal, Mapping):
                status = str(signal.get("status", "") or "").strip().lower()
                passed = bool(signal.get("passed", status == "pass"))
                verification = {
                    "status": "pass" if passed else "fail",
                    "passed": passed,
                    "stage": str(signal.get("stage", "") or ""),
                    "exec_ran": bool(signal.get("exec_ran", False)),
                }

        oracle_meta: dict[str, Any] = {"components": {"grounding": score}}
        if verification:
            oracle_meta["verification_signal"] = verification

        return SimpleNamespace(score=score, reason="stub", meta=oracle_meta)


def _build_swarm_for_rate_test() -> SwarmManager:
    verified_meta = {
        "tool_first": {
            "attempted": True,
            "verification": {
                "status": "pass",
                "passed": True,
                "stage": "exec",
                "exec_ran": True,
            },
        }
    }
    agents = [
        _FixedAgent(name="verified-agent", text="verified-answer", meta=verified_meta, cost_prior=0.8),
        _FixedAgent(name="plain-agent", text="plain-answer", meta={}, cost_prior=0.2),
    ]
    oracle = _OracleByText({"verified-answer": 0.62, "plain-answer": 0.95})
    return SwarmManager(agents, oracle=oracle, mode="v3")


def test_v3_selector_prefers_tool_verified_before_higher_oracle_score() -> None:
    swarm = SwarmManager([], mode="v3")
    high_oracle = _candidate(
        agent="high-oracle",
        text="high",
        score=0.96,
        latency=120.0,
        cost=60.0,
    )
    tool_verified = _candidate(
        agent="tool-verified",
        text="verified",
        score=0.61,
        latency=120.0,
        cost=60.0,
        meta={
            "tool_first": {
                "attempted": True,
                "verification": {"status": "pass", "passed": True, "stage": "exec", "exec_ran": True},
            }
        },
        oracle_meta={"verification_signal": {"status": "pass", "passed": True, "stage": "exec", "exec_ran": True}},
    )

    best, _confidence, pareto = swarm._select_best_v3([high_oracle, tool_verified], budget_mode="balanced")

    assert best["agent"] == "tool-verified"
    assert pareto["selector"]["rule"] == "tool-verified"
    assert pareto["selector"]["scope"] == "global-tool-verified"


def test_v3_selector_uses_stable_shorter_cleaner_fallback_on_oracle_tie() -> None:
    swarm = SwarmManager([], mode="v3")
    noisy = _candidate(
        agent="noisy",
        text="```python\n# TODO refine\nprint(42)\n```\n\n",
        score=0.80,
        latency=101.0,
        cost=49.0,
        confidence=0.80,
    )
    clean = _candidate(
        agent="clean",
        text="Final answer: 42",
        score=0.80,
        latency=101.0,
        cost=49.0,
        confidence=0.80,
    )

    best_a, _confidence_a, pareto_a = swarm._select_best_v3([noisy, clean], budget_mode="balanced")
    best_b, _confidence_b, pareto_b = swarm._select_best_v3([noisy, clean], budget_mode="balanced")

    assert best_a["agent"] == "clean"
    assert best_b["agent"] == "clean"
    assert pareto_a["selector"]["rule"] == "fallback-shorter-cleaner"
    assert pareto_b["selector"]["rule"] == "fallback-shorter-cleaner"


def test_v3_swarm_run_preserves_tool_verification_metadata_and_rate() -> None:
    swarm = _build_swarm_for_rate_test()
    out = swarm.run("verify tool metadata", mode="v3", rounds=1, top_k=2)

    assert out["best"]["agent"] == "verified-agent"
    assert out["best"]["tool_verified"] is True
    assert out["trace"]["swarm"]["tool_verification_rate"] == pytest.approx(0.5)
    assert out["trace"]["swarm"]["tool_verification"]["verified_candidates"] == 1
    assert out["tool_verification_rate"] == pytest.approx(0.5)

    oracle_rows = out["trace"]["oracle"]["scores"]
    assert any(bool(row.get("tool_verified", False)) for row in oracle_rows)
    assert any((row.get("tool_verification", {}) or {}).get("status") == "pass" for row in oracle_rows)


def test_orchestration_run_swarm_keeps_tool_verification_rate_visible(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    app = MoAAPrime(seed=99, mode="v3")
    app.swarm_v3 = _build_swarm_for_rate_test()

    out = app.run_swarm(
        "verify orchestration metadata path",
        mode="v3",
        rounds=1,
        top_k=2,
        dual_gate=True,
        dual_gate_config={"high_ambiguity_threshold": 0.0},
    )

    assert out["trace"]["swarm"]["dual_gate"]["enabled"] is True
    assert out["trace"]["swarm"]["tool_verification_rate"] == pytest.approx(0.5)
    assert out["answer_object"]["trace"]["swarm"]["tool_verification_rate"] == pytest.approx(0.5)


def test_swarm_build_candidate_falls_back_for_signature_mismatch_only() -> None:
    swarm = SwarmManager([], mode="v3")
    candidate = swarm._build_candidate(
        agent=_NoTaskIdAgent(),
        prompt="hello",
        task_id="sig-mismatch",
        round_idx=0,
        rank_idx=0,
        mode="v3",
    )
    assert candidate["agent"] == "no-taskid-agent"
    assert candidate["text"] == "ok"


def test_swarm_build_candidate_reraises_internal_type_error() -> None:
    swarm = SwarmManager([], mode="v3")
    with pytest.raises(TypeError, match="internal type error"):
        swarm._build_candidate(
            agent=_InternalTypeErrorAgent(),
            prompt="hello",
            task_id="internal-type-error",
            round_idx=0,
            rank_idx=0,
            mode="v3",
        )
