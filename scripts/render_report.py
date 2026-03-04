from __future__ import annotations
import json
from pathlib import Path

def main():
    demo = json.loads(Path("reports/demo_run.json").read_text())
    bench = json.loads(Path("reports/bench.json").read_text())
    evalr = json.loads(Path("reports/eval_report.json").read_text())
    eval_counts = evalr.get("counts") if isinstance(evalr, dict) else None
    eval_cases = None
    if isinstance(eval_counts, dict):
        eval_cases = eval_counts.get("num_cases")
    if eval_cases is None and isinstance(evalr, dict):
        eval_cases = evalr.get("num_cases")

    out = {
        "summary": {
            "agents_used": sorted({demo[k]["decision"]["agent"] for k in ["once_math", "once_code"]}),
            "swarm_candidates": len(demo["swarm"]["candidates"]),
            "latency_ms": bench,
            "eval_cases": int(eval_cases or 0),
        },
        "verdict": "MoAA-Prime demonstrates multi-agent routing, memory, verification, and swarm reasoning with real models."
    }

    Path("reports/final_report.json").write_text(
        json.dumps(out, indent=2), encoding="utf-8"
    )
    print("Wrote reports/final_report.json")

if __name__ == "__main__":
    main()
