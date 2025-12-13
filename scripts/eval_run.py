from __future__ import annotations

from moaa_prime.eval.runner import EvalCase, EvalRunner
from moaa_prime.eval.report import write_json_report


def main() -> int:
    cases = [
        EvalCase(case_id="math_1", prompt="Solve: 2x + 3 = 7. Return only x.", mode="once"),
        EvalCase(case_id="code_1", prompt="Write Python: function add(a,b) returns a+b", mode="once"),
        EvalCase(case_id="swarm_1", prompt="Explain why 1/0 is undefined, then give a safe Python example.", mode="swarm"),
    ]

    runner = EvalRunner()
    results = runner.run(cases)
    write_json_report(results, "reports/eval_report.json")
    print("Wrote reports/eval_report.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
