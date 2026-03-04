from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# Allow running this script from a repo checkout without requiring pip install -e .
_SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if _SRC_DIR.exists() and str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from moaa_prime.policy.tool_first import (
    extract_python_source,
    run_code_tool_first,
    run_math_tool_first,
    verify_python_source,
)


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


def _tool_math(prompt: str) -> str:
    out = run_math_tool_first(prompt)
    if not out.success:
        return ""
    return out.text


def _score_math_case(prompt: str, expected: set[str], solver) -> bool:
    got = _normalized_numbers(solver(prompt))
    return expected.issubset(got)


def _baseline_non_tool_code(prompt: str) -> bool:
    extracted = extract_python_source(prompt)
    if extracted is None:
        return False
    source, _method = extracted
    v = verify_python_source(source, execute=True)
    return bool(v.passed)


def _tool_code(prompt: str) -> bool:
    out = run_code_tool_first(prompt, max_retries=2, execute=True)
    return bool(out.success)


def _pass_rate(values: list[bool]) -> float:
    if not values:
        return 0.0
    return float(sum(1 for v in values if v) / len(values))


def _count_passed(values: list[bool]) -> int:
    return int(sum(1 for v in values if v))


def _section_block(
    *,
    num_cases: int,
    baseline_pass_rate: float,
    tool_first_pass_rate: float,
    cases: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    rows = list(cases or [])
    baseline_flags = [bool(r.get("baseline_pass", False)) for r in rows] if rows else []
    tool_flags = [bool(r.get("tool_first_pass", False)) for r in rows] if rows else []
    passed = _count_passed(tool_flags) if rows else int(round(float(tool_first_pass_rate) * float(max(0, num_cases))))
    baseline_passed = (
        _count_passed(baseline_flags) if rows else int(round(float(baseline_pass_rate) * float(max(0, num_cases))))
    )
    scored_cases = int(num_cases)
    block: dict[str, object] = {
        "num_cases": int(num_cases),
        "scored_cases": scored_cases,
        "passed": int(passed),
        "baseline_passed": int(baseline_passed),
        "baseline_pass_rate": float(baseline_pass_rate),
        "tool_first_pass_rate": float(tool_first_pass_rate),
        "pass_rate_delta": float(tool_first_pass_rate - baseline_pass_rate),
    }
    if rows:
        block["cases"] = rows
    return block


def main() -> int:
    math_cases = [
        {"id": "math_linear", "prompt": "Solve 3*x + 1 = 13 for x", "expected": {"4"}},
        {"id": "math_quadratic", "prompt": "Solve x^2 - 7*x + 10 = 0 for x", "expected": {"2", "5"}},
        {"id": "math_eval", "prompt": "Evaluate (17 - 5) * 3", "expected": {"36"}},
    ]
    code_cases = [
        {
            "id": "code_missing_colon",
            "prompt": "```python\ndef add(a, b)\n    return a + b\n```",
        },
        {
            "id": "code_bad_return",
            "prompt": "```python\ndef add(a, b):\n    return a +\n```",
        },
        {
            "id": "code_exec_safe",
            "prompt": "```python\ndef square(x):\n    return x * x\n```",
        },
    ]

    math_rows = []
    for case in math_cases:
        baseline_ok = _score_math_case(case["prompt"], case["expected"], _baseline_non_tool_math)
        tool_ok = _score_math_case(case["prompt"], case["expected"], _tool_math)
        math_rows.append(
            {
                "id": case["id"],
                "baseline_pass": baseline_ok,
                "tool_first_pass": tool_ok,
            }
        )

    code_rows = []
    for case in code_cases:
        baseline_ok = _baseline_non_tool_code(case["prompt"])
        tool_ok = _tool_code(case["prompt"])
        code_rows.append(
            {
                "id": case["id"],
                "baseline_pass": baseline_ok,
                "tool_first_pass": tool_ok,
            }
        )

    math_baseline = _pass_rate([bool(r["baseline_pass"]) for r in math_rows])
    math_tool = _pass_rate([bool(r["tool_first_pass"]) for r in math_rows])
    code_baseline = _pass_rate([bool(r["baseline_pass"]) for r in code_rows])
    code_tool = _pass_rate([bool(r["tool_first_pass"]) for r in code_rows])

    overall_baseline = _pass_rate(
        [bool(r["baseline_pass"]) for r in math_rows] + [bool(r["baseline_pass"]) for r in code_rows]
    )
    overall_tool = _pass_rate(
        [bool(r["tool_first_pass"]) for r in math_rows] + [bool(r["tool_first_pass"]) for r in code_rows]
    )

    math_block = _section_block(
        num_cases=len(math_rows),
        baseline_pass_rate=math_baseline,
        tool_first_pass_rate=math_tool,
        cases=math_rows,
    )
    code_block = _section_block(
        num_cases=len(code_rows),
        baseline_pass_rate=code_baseline,
        tool_first_pass_rate=code_tool,
        cases=code_rows,
    )
    overall_block = _section_block(
        num_cases=len(math_rows) + len(code_rows),
        baseline_pass_rate=overall_baseline,
        tool_first_pass_rate=overall_tool,
    )

    counts = {
        "num_cases": int(overall_block["num_cases"]),
        "scored_cases": int(overall_block["scored_cases"]),
        "passed": int(overall_block["passed"]),
    }

    payload = {
        "suite": "pr1_tool_first",
        "schema_version": "1.1",
        "counts": counts,
        "num_cases": int(counts["num_cases"]),
        "scored_cases": int(counts["scored_cases"]),
        "passed": int(counts["passed"]),
        "pass_rate": float(overall_block["tool_first_pass_rate"]),
        "summary": {
            "counts": counts,
            "metrics": {
                "baseline_pass_rate": float(overall_block["baseline_pass_rate"]),
                "tool_first_pass_rate": float(overall_block["tool_first_pass_rate"]),
                "pass_rate_delta": float(overall_block["pass_rate_delta"]),
            },
            "categories": {
                "math": {
                    "num_cases": int(math_block["num_cases"]),
                    "scored_cases": int(math_block["scored_cases"]),
                    "passed": int(math_block["passed"]),
                    "baseline_pass_rate": float(math_block["baseline_pass_rate"]),
                    "tool_first_pass_rate": float(math_block["tool_first_pass_rate"]),
                    "pass_rate_delta": float(math_block["pass_rate_delta"]),
                },
                "code": {
                    "num_cases": int(code_block["num_cases"]),
                    "scored_cases": int(code_block["scored_cases"]),
                    "passed": int(code_block["passed"]),
                    "baseline_pass_rate": float(code_block["baseline_pass_rate"]),
                    "tool_first_pass_rate": float(code_block["tool_first_pass_rate"]),
                    "pass_rate_delta": float(code_block["pass_rate_delta"]),
                },
            },
        },
        "math": math_block,
        "code": code_block,
        "overall": overall_block,
    }

    reports = Path("reports")
    reports.mkdir(parents=True, exist_ok=True)
    out_primary = reports / "tool_first_eval.json"
    out_compat = reports / "eval_tool_first.json"
    serialized = json.dumps(payload, indent=2)
    out_primary.write_text(serialized, encoding="utf-8")
    out_compat.write_text(serialized, encoding="utf-8")
    print(f"Wrote {out_primary}")
    print(f"Wrote {out_compat}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
