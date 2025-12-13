from __future__ import annotations

import json
import os
import time
from pathlib import Path

from moaa_prime.core.app import MoAAPrime


def timed(fn, n: int = 10) -> float:
    t0 = time.perf_counter()
    for _ in range(n):
        fn()
    t1 = time.perf_counter()
    return (t1 - t0) / n


def main() -> int:
    app = MoAAPrime()

    once_ms = timed(lambda: app.run_once("2+2=?", task_id="bench"), n=30) * 1000.0
    swarm_ms = timed(lambda: app.run_swarm("Explain 2+2", task_id="bench"), n=10) * 1000.0

    provider = (os.getenv("MOAA_LLM_PROVIDER") or "stub").strip().lower()
    model = os.getenv("MOAA_OLLAMA_MODEL") or ""
    note = (
        f"Provider={provider}. "
        + (f"Ollama model={model}." if provider == "ollama" else "Using StubLLMClient.")
    )

    report = {
        "once_avg_ms": once_ms,
        "swarm_avg_ms": swarm_ms,
        "note": note,
    }

    Path("reports").mkdir(parents=True, exist_ok=True)
    Path("reports/bench.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("Wrote reports/bench.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
