from __future__ import annotations

from collections.abc import Callable

import pytest

from moaa_prime.agents.code_agent import CodeAgent
from moaa_prime.contracts import Contract
from moaa_prime.oracle.verifier import OracleV2, OracleVerifier
from moaa_prime.policy import tool_first
from moaa_prime.policy.tool_first import CodeVerification, run_code_tool_first
from moaa_prime.tools import extract_python_source_deterministic, verify_python_source_deterministic


def _verification_meta(*, passed: bool, stage: str, exec_ran: bool) -> dict[str, object]:
    status = "pass" if passed else "fail"
    payload: dict[str, object] = {
        "status": status,
        "passed": passed,
        "stage": stage,
        "exec_ran": exec_ran,
    }
    if passed:
        payload["error_type"] = None
        payload["error_message"] = None
    else:
        payload["error_type"] = "RuntimeError"
        payload["error_message"] = "synthetic"
    return {"tool_first": {"verification": payload}}


def test_pr2_sandbox_pass_path_captures_stdout_deterministically() -> None:
    source = "class Probe:\n    print('sandbox-ok')\n"

    outcome = verify_python_source_deterministic(source, execute=True, filename="<test-pr2-pass>")

    assert outcome.status == "pass"
    assert outcome.passed is True
    assert outcome.stage == "exec"
    assert outcome.exec_ran is True
    assert outcome.stdout == "sandbox-ok\n"
    assert outcome.error_type is None
    assert outcome.error_message is None


@pytest.mark.parametrize(
    ("prompt", "expected_source", "expected_method"),
    [
        (
            "Use this:\n```python\ndef add(a, b):\n    return a + b\n```",
            "def add(a, b):\n    return a + b",
            "fenced_block",
        ),
        (
            "Please fix this function: def mul(a, b):\n    return a * b",
            "def mul(a, b):\n    return a * b",
            "inline_def",
        ),
        (
            "def sub(a, b):\n    return a - b",
            "def sub(a, b):\n    return a - b",
            "inline_def",
        ),
    ],
)
def test_pr2_sandbox_extracts_python_source_deterministically(
    prompt: str,
    expected_source: str,
    expected_method: str,
) -> None:
    extracted = extract_python_source_deterministic(prompt)
    assert extracted == (expected_source, expected_method)


def test_pr2_sandbox_compile_fail_path_is_structured_and_deterministic() -> None:
    source = "def add(a, b)\n    return a + b\n"

    outcome = verify_python_source_deterministic(source, execute=True, filename="<test-pr2-compile-fail>")

    assert outcome.status == "fail"
    assert outcome.passed is False
    assert outcome.stage == "compile"
    assert outcome.error_type == "SyntaxError"
    assert outcome.error_message
    assert outcome.line == 1
    assert isinstance(outcome.column, int)
    assert outcome.exec_ran is False
    assert outcome.stdout == ""


def test_pr2_sandbox_exec_fail_path_is_structured_and_deterministic() -> None:
    source = "class Probe:\n    raise ValueError('boom')\n"

    outcome = verify_python_source_deterministic(source, execute=True, filename="<test-pr2-exec-fail>")

    assert outcome.status == "fail"
    assert outcome.passed is False
    assert outcome.stage == "exec"
    assert outcome.error_type == "ValueError"
    assert outcome.error_message == "boom"
    assert outcome.exec_ran is True
    assert outcome.stdout == ""


@pytest.mark.parametrize(
    "oracle_factory",
    [
        pytest.param(lambda: OracleVerifier(), id="oracle-v1"),
        pytest.param(lambda: OracleV2(seed=11), id="oracle-v2"),
    ],
)
def test_pr2_oracle_confidence_uses_verifier_signal_deterministically_and_backcompat(
    oracle_factory: Callable[[], OracleVerifier | OracleV2],
) -> None:
    oracle = oracle_factory()
    prompt = "Write Python code for add(a, b)."
    answer = "def add(a, b):\n    return a + b"

    baseline = oracle.score(prompt, answer)
    assert baseline == oracle.score(prompt, answer)
    assert baseline == oracle.score(prompt, answer, answer_metadata={"noise": {"k": "v"}})
    assert baseline == oracle.score(prompt, answer, answer_metadata={"tool_first": {}})

    pass_compile = oracle.score(
        prompt,
        answer,
        answer_metadata=_verification_meta(passed=True, stage="compile", exec_ran=False),
    )
    pass_exec = oracle.score(
        prompt,
        answer,
        answer_metadata=_verification_meta(passed=True, stage="exec", exec_ran=True),
    )
    fail_compile = oracle.score(
        prompt,
        answer,
        answer_metadata=_verification_meta(passed=False, stage="compile", exec_ran=False),
    )
    fail_exec = oracle.score(
        prompt,
        answer,
        answer_metadata=_verification_meta(passed=False, stage="exec", exec_ran=True),
    )

    assert pass_compile - baseline == pytest.approx(0.05)
    assert pass_exec - baseline == pytest.approx(0.07)
    assert fail_compile - baseline == pytest.approx(-0.08)
    assert fail_exec - baseline == pytest.approx(-0.10)

    with_signal = oracle.verdict(
        prompt,
        answer,
        answer_metadata=_verification_meta(passed=True, stage="exec", exec_ran=True),
    )
    assert "verifier=pass" in with_signal.reason

    without_signal = oracle.verdict(prompt, answer)
    if isinstance(oracle, OracleVerifier):
        assert without_signal.meta is None
    else:
        assert without_signal.meta is not None
        assert "verification_delta" not in without_signal.meta


def test_pr2_repair_loop_uses_verifier_result_fields_for_rule_application(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_verify = tool_first.verify_python_source
    original_apply = tool_first._apply_repair

    verify_calls = 0
    seen_verifications: list[CodeVerification] = []

    def _verify_stub(source: str, *, execute: bool = True) -> CodeVerification:
        nonlocal verify_calls
        verify_calls += 1
        if verify_calls == 1:
            return CodeVerification(
                passed=False,
                stage="compile",
                error_type="SyntaxError",
                error_message="expected ':'",
                line=4,
                column=14,
                exec_ran=False,
            )
        return original_verify(source, execute=execute)

    def _apply_spy(source: str, verification: CodeVerification):
        seen_verifications.append(verification)
        return original_apply(source, verification)

    monkeypatch.setattr(tool_first, "verify_python_source", _verify_stub)
    monkeypatch.setattr(tool_first, "_apply_repair", _apply_spy)

    source = "def keep():\n    return 1\n\ndef target(x)\n    return x\n"
    outcome = run_code_tool_first(source, max_retries=1, execute=False)

    assert outcome.success is True
    assert outcome.repairs == ("add_missing_colon",)
    assert "def target(x):" in (outcome.final_code or "")
    assert seen_verifications
    assert seen_verifications[0].stage == "compile"
    assert seen_verifications[0].error_type == "SyntaxError"
    assert seen_verifications[0].line == 4


class _PromptOnlyLLM:
    def generate(self, prompt: str, *, system: str = "", model: str | None = None):
        raise AssertionError(f"LLM should not be called for prompt-source path: {prompt}, {system}, {model}")


def test_pr2_code_agent_tool_first_meta_keeps_verifier_fields_in_prompt_path() -> None:
    agent = CodeAgent(
        Contract(name="code-agent", domains=["code"]),
        llm=_PromptOnlyLLM(),
        max_tool_retries=0,
    )

    result = agent.handle("def add(a, b)\n    return a + b", task_id="pr2-code-agent-fields")
    tool_meta = result.meta["tool_first"]
    verification = tool_meta["verification"]

    assert tool_meta["source"] == "prompt"
    assert tool_meta["attempted"] is True
    assert tool_meta["success"] is False
    assert verification["status"] == "fail"
    assert verification["stage"] == "compile"
    assert verification["error_type"] == "SyntaxError"
    assert verification["error_message"]
    assert verification["line"] == 1
    assert verification["exec_ran"] is False
