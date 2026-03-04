from __future__ import annotations

import os
import sys
from pathlib import Path

# Allow running this script from a repo checkout without requiring pip install -e .
_SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if _SRC_DIR.exists() and str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from moaa_prime.core.app import MoAAPrime
from moaa_prime.util.json_safe import dumps_pretty


def main() -> int:
    mode = (os.getenv("MOAA_DEMO_MODE") or "v2").strip().lower()
    seed = int(os.getenv("MOAA_DEMO_SEED") or "7")

    app = MoAAPrime(mode=mode, seed=seed)

    swarm = app.run_swarm(
        "Explain why 1/0 is undefined, then give a safe Python example.",
        task_id="demo",
        mode=mode,
        rounds=3,
        top_k=2,
        cross_check=False,
        run_id=f"demo_{mode}",
    )

    out = {
        "mode": mode,
        "seed": seed,
        "once_math": app.run_once("Solve: 2x + 3 = 7. Return only x.", task_id="demo", mode=mode),
        "once_code": app.run_once("Write Python: function add(a,b) returns a+b", task_id="demo", mode=mode),
        "swarm": swarm,
        "evolve": app.evolve_contracts(
            {
                "math-agent": {"oracle_score": 0.92, "eval_success": 0.90, "budget_efficiency": 0.82},
                "code-agent": {"oracle_score": 0.73, "eval_success": 0.68, "budget_efficiency": 0.76},
            },
            mode=mode,
        ),
    }

    Path("reports").mkdir(parents=True, exist_ok=True)
    Path("reports/demo_run.json").write_text(dumps_pretty(out), encoding="utf-8")
    print("Wrote reports/demo_run.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
