from __future__ import annotations

import json
from pathlib import Path

from moaa_prime.core.app import MoAAPrime


def main() -> int:
    app = MoAAPrime()

    out = {
        "once_math": app.run_once("Solve: 2x + 3 = 7. Return only x.", task_id="demo"),
        "once_code": app.run_once("Write Python: function add(a,b) returns a+b", task_id="demo"),
        "swarm": app.run_swarm("Explain why 1/0 is undefined, then give a safe Python example.", task_id="demo"),
        "evolve": app.evolve_contracts({"math-agent": 1.0, "code-agent": 0.2}),
    }

    Path("reports").mkdir(parents=True, exist_ok=True)
    Path("reports/demo_run.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print("Wrote reports/demo_run.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
