from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Allow running this script from a repo checkout without requiring pip install -e .
_SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if _SRC_DIR.exists() and str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from moaa_prime.eval.runner import EvalCase, EvalRunner
from moaa_prime.eval.report import write_json_report


def _load_cases() -> list[EvalCase]:
    path = Path("demos/demo_cases.json")
    if not path.exists():
        return [
            EvalCase(case_id="math_1", prompt="Solve: 2x + 3 = 7. Return only x.", mode="once"),
            EvalCase(case_id="code_1", prompt="Write Python: function add(a,b) returns a+b", mode="once"),
            EvalCase(
                case_id="swarm_1",
                prompt="Explain why 1/0 is undefined, then give a safe Python example.",
                mode="swarm",
            ),
        ]

    payload = json.loads(path.read_text(encoding="utf-8"))
    cases = []
    for row in payload.get("cases", []):
        cases.append(EvalCase(case_id=str(row["id"]), prompt=str(row["prompt"]), mode=str(row.get("mode", "once"))))
    return cases


def main() -> int:
    mode = (os.getenv("MOAA_EVAL_MODE") or "v3").strip().lower()
    seed = int(os.getenv("MOAA_EVAL_SEED") or "11")

    runner = EvalRunner(model_mode=mode, seed=seed)
    results = runner.run(_load_cases())
    write_json_report(results, "reports/eval_report.json")
    print("Wrote reports/eval_report.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
