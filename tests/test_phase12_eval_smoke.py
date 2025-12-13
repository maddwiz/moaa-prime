from __future__ import annotations

from moaa_prime.eval.runner import EvalCase, EvalRunner


def test_phase12_eval_runner_smoke() -> None:
    runner = EvalRunner()
    cases = [
        EvalCase(case_id="t1", prompt="2+2=?", mode="once"),
    ]
    results = runner.run(cases)
    assert len(results) == 1
    assert results[0].case_id == "t1"
    assert isinstance(results[0].output, dict)
