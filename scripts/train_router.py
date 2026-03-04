from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Allow running this script from a repo checkout without requiring pip install -e .
_SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if _SRC_DIR.exists() and str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from moaa_prime.router.training import train_and_save_router_v3


def main() -> int:
    seed = int(os.getenv("MOAA_ROUTER_TRAIN_SEED") or "17")
    trace_dir = os.getenv("MOAA_TRACE_DIR") or "reports/traces"
    dataset_path = os.getenv("MOAA_ROUTER_DATASET") or "datasets/router_training.jsonl"
    model_path = os.getenv("MOAA_ROUTER_V3_MODEL") or "models/router_v3.pt"

    summary = train_and_save_router_v3(
        seed=seed,
        trace_dir=trace_dir,
        dataset_path=dataset_path,
        model_path=model_path,
    )

    Path("reports").mkdir(parents=True, exist_ok=True)
    report_path = Path("reports/router_train_report.json")
    report_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(f"Wrote {report_path}")
    print(f"Wrote {model_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
