from __future__ import annotations

import re
from collections.abc import Callable

import pytest

from moaa_prime.agents.code_agent import CodeAgent
from moaa_prime.contracts import Contract
from moaa_prime.core.app import MoAAPrime
from moaa_prime.llm.client import LLMResponse
from moaa_prime.policy import tool_first
from moaa_prime.policy.tool_first import CodeVerification, run_code_tool_first, run_math_tool_first


_NUMBER_RE = re.compile(r"(?<![A-Za-z_])[+-]?\d+(?:\.\d+)?")
_LINEAR_EQ_RE = re.compile(r"([+-]?\d+)\s*\*?\s*x\s*([+-]\s*\d+)?\s*=\s*([+-]?\d+)", re.IGNORECASE)


def _normalized_numbers(text: str) -> set[str]:
    out: set[str] = set()
    for token in _NUMBER_RE.findall(text):
        value = float(token)
        if abs(value - round(value)) < 1.0e-9:
            out.add(str(int(round(value))))
        else:
            out.add(f"{value:.6g}")
    return out


def _baseline_non_tool_math(prompt: str) -> str:
    match = _LINEAR_EQ_RE.search(prompt)
    if match is None:
        return ""

    a = int(match.group(1))
    b = int((match.group(2) or "+0").replace(" ", ""))
    c = int(match.group(3))
    if a == 0:
        return ""

    x_value = (c - b) / a
    if abs(x_value - round(x_value)) < 1.0e-9:
        rendered = str(int(round(x_value)))
    else:
        rendered = f"{x_value:.6g}"
    return f"x = {rendered}"


def _tool_first_math_text(prompt: str) -> str:
    outcome = run_math_tool_first(prompt)
    if not outcome.success:
        return ""
    return outcome.text


def _score_math_cases(cases: list[tuple[str, set[str]]], solver: Callable[[str], str]) -> float:
    hits = 0
    for prompt, expected in cases:
        numbers = _normalized_numbers(solver(prompt))
        if expected.issubset(numbers):
            hits += 1
    return hits / float(len(cases))


def test_pr1_math_tool_first_routes_to_sympy(monkeypatch: pytest.MonkeyPatch) -> None:
    if tool_first.sp is None:
        pytest.skip("SymPy is unavailable")

    solve_calls: list[tuple[tuple[object, ...], dict[str, object]]] = []
    original_solve = tool_first.sp.solve

    def _solve_spy(*args: object, **kwargs: object):
        solve_calls.append((args, kwargs))
        return original_solve(*args, **kwargs)

    monkeypatch.setattr(tool_first.sp, "solve", _solve_spy)

    outcome = run_math_tool_first("Solve 3*x + 1 = 13 for x")

    assert outcome.attempted is True
    assert outcome.success is True
    assert outcome.mode == "equation"
    assert outcome.solver == "sympy"
    assert solve_calls, "Expected SymPy solve to be called for solvable equation prompt."
    assert {"4"}.issubset(_normalized_numbers(outcome.text))


def test_pr1_code_tool_first_verifies_and_has_bounded_repair_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    verify_calls: list[str] = []
    repair_calls: list[str] = []

    def _verify_stub(source: str, *, execute: bool = True) -> CodeVerification:
        _ = execute
        verify_calls.append(source)
        return CodeVerification(
            passed=False,
            stage="compile",
            error_type="SyntaxError",
            error_message="synthetic failure",
            line=1,
            column=1,
            exec_ran=False,
        )

    def _repair_stub(source: str, verification: CodeVerification):
        _ = verification
        repair_calls.append(source)
        next_idx = len(repair_calls)
        return f"{source}\n# synthetic-repair-{next_idx}", "synthetic_repair"

    monkeypatch.setattr(tool_first, "verify_python_source", _verify_stub)
    monkeypatch.setattr(tool_first, "_apply_repair", _repair_stub)

    outcome = run_code_tool_first(
        "def add(a, b)\n    return a + b",
        max_retries=2,
        execute=True,
    )

    assert outcome.attempted is True
    assert outcome.success is False
    assert len(verify_calls) == 3  # initial verify + 2 bounded retries
    assert len(repair_calls) == 2
    assert outcome.retries_used == 2
    assert outcome.max_retries == 2
    assert outcome.repairs == ("synthetic_repair", "synthetic_repair")


def test_pr1_tool_first_math_correctness_signal_beats_non_tool_baseline() -> None:
    cases: list[tuple[str, set[str]]] = [
        ("Solve 3*x + 1 = 13 for x", {"4"}),
        ("Solve x^2 - 7*x + 10 = 0 for x", {"2", "5"}),
        ("Evaluate (17 - 5) * 3", {"36"}),
    ]

    baseline_score_a = _score_math_cases(cases, _baseline_non_tool_math)
    baseline_score_b = _score_math_cases(cases, _baseline_non_tool_math)
    tool_score_a = _score_math_cases(cases, _tool_first_math_text)
    tool_score_b = _score_math_cases(cases, _tool_first_math_text)

    assert baseline_score_a == baseline_score_b
    assert tool_score_a == tool_score_b
    assert tool_score_a > baseline_score_a, (
        "Expected deterministic tool-first math correctness to exceed non-tool baseline score. "
        f"tool_first={tool_score_a:.3f}, baseline={baseline_score_a:.3f}"
    )


def test_pr1_math_agent_emits_tool_first_meta_in_run_once() -> None:
    app = MoAAPrime(seed=17)
    out = app.run_once("Solve 2x + 3 = 7 for x", mode="v1")

    assert out["result"]["agent"] == "math-agent"
    tool_meta = out["result"]["meta"]["tool_first"]
    assert tool_meta["attempted"] is True
    assert tool_meta["success"] is True
    assert {"2"}.issubset(_normalized_numbers(out["result"]["text"]))


def test_pr1_code_agent_uses_llm_proposal_then_verify_repair() -> None:
    class _LLMStub:
        def generate(self, prompt: str, *, system: str = "", model: str | None = None) -> LLMResponse:
            _ = (prompt, system, model)
            return LLMResponse(
                text="def add(a, b)\n    return a + b",
                model="stub-proposal",
                usage={},
            )

    agent = CodeAgent(
        Contract(name="code-agent", domains=["code"]),
        llm=_LLMStub(),
        max_tool_retries=2,
    )

    result = agent.handle("Write Python add(a, b) function", task_id="pr1-code-proposal")
    tool_meta = result.meta["tool_first"]

    assert tool_meta["source"] == "llm_proposal"
    assert tool_meta["success"] is True
    assert "Verified" in result.text
    assert "def add(a, b):" in result.text
