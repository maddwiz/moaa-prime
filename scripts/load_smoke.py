from __future__ import annotations

import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from pathlib import Path
from typing import Any

# Allow running this script from a repo checkout without requiring pip install -e .
_SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if _SRC_DIR.exists() and str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from moaa_prime.core.app import MoAAPrime


DUAL_GATE_CONFIG: dict[str, float] = {
    "low_confidence_threshold": 0.66,
    "high_ambiguity_threshold": 0.85,
    "max_single_score_for_dual": 0.82,
}

DEFAULT_PROMPTS: tuple[str, ...] = (
    "Solve 2x + 3 = 7. Return only x.",
    "Write Python function add(a,b) that returns a + b.",
    "Explain why dividing by zero is undefined in arithmetic.",
    "Classify this intent as math or code with one word: Solve 6x = 24.",
    "Memory setup: store token smoke-1 with value 9 for this task.",
    "Memory recall: return the stored token/value for smoke-1 in format `smoke-1|<value>`.",
)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(float(v) for v in values)
    idx = int(round((len(ordered) - 1) * float(p)))
    idx = max(0, min(len(ordered) - 1, idx))
    return float(ordered[idx])


def _run_swarm_once(
    app: MoAAPrime,
    *,
    prompt: str,
    iteration: int,
    timeout_sec: float,
) -> tuple[bool, dict[str, Any]]:
    timeout = max(1.0, float(timeout_sec))

    def _task() -> dict[str, Any]:
        return app.run_swarm(
            prompt,
            task_id=f"load-smoke-{iteration}",
            mode="v3",
            rounds=1,
            top_k=1,
            budget={"mode": "cheap"},
            dual_gate=True,
            dual_gate_config=DUAL_GATE_CONFIG,
        )

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(_task)
        try:
            payload = dict(future.result(timeout=timeout))
        except FutureTimeoutError:
            return False, {
                "error": "timeout",
                "timeout_sec": timeout,
            }
        except Exception as exc:  # pragma: no cover - defensive
            return False, {
                "error": "exception",
                "message": str(exc),
            }

    proxy_ms = _safe_float(payload.get("avg_latency_proxy"), default=0.0)
    return True, {
        "latency_ms": float(proxy_ms),
        "oracle_score": _safe_float(((payload.get("best", {}) or {}).get("oracle", {}) or {}).get("score"), default=0.0),
        "winner_agent": str((payload.get("best", {}) or {}).get("agent", "")),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic load smoke checks for production readiness.")
    parser.add_argument("--output", default="reports/load_smoke.json")
    parser.add_argument("--iters", type=int, default=50)
    parser.add_argument("--timeout-sec", type=float, default=20.0)
    parser.add_argument("--max-retries", type=int, default=1)
    parser.add_argument("--p95-budget-ms", type=float, default=2500.0)
    parser.add_argument("--error-rate-budget", type=float, default=0.01)
    args = parser.parse_args()

    total_requests = max(1, int(args.iters))
    timeout_sec = max(1.0, float(args.timeout_sec))
    max_retries = max(0, int(args.max_retries))
    p95_budget_ms = max(1.0, float(args.p95_budget_ms))
    error_rate_budget = max(0.0, float(args.error_rate_budget))

    app = MoAAPrime(mode="v3", seed=37)
    provider = (os.getenv("MOAA_LLM_PROVIDER") or "stub").strip().lower()

    rows: list[dict[str, Any]] = []
    latencies: list[float] = []
    failures = 0

    for idx in range(total_requests):
        prompt = DEFAULT_PROMPTS[idx % len(DEFAULT_PROMPTS)]
        success = False
        last_details: dict[str, Any] = {}
        attempts_used = 0

        for attempt in range(max_retries + 1):
            attempts_used = attempt + 1
            ok, details = _run_swarm_once(
                app,
                prompt=prompt,
                iteration=idx,
                timeout_sec=timeout_sec,
            )
            last_details = details
            if ok:
                success = True
                latencies.append(float(details["latency_ms"]))
                break

        if not success:
            failures += 1

        rows.append(
            {
                "iteration": int(idx),
                "success": bool(success),
                "attempts": int(attempts_used),
                "details": last_details,
            }
        )

    successes = int(total_requests - failures)
    error_rate = float(failures / max(1, total_requests))
    p50_latency_ms = _percentile(latencies, 0.50)
    p95_latency_ms = _percentile(latencies, 0.95)

    metrics = {
        "request_count": int(total_requests),
        "successes": int(successes),
        "failures": int(failures),
        "error_rate": float(error_rate),
        "min_latency_ms": float(min(latencies) if latencies else 0.0),
        "max_latency_ms": float(max(latencies) if latencies else 0.0),
        "mean_latency_ms": float(sum(latencies) / len(latencies)) if latencies else 0.0,
        "p50_latency_ms": float(p50_latency_ms),
        "p95_latency_ms": float(p95_latency_ms),
    }

    checks = {
        "error_rate_within_budget": bool(error_rate <= error_rate_budget),
        "p95_latency_within_budget": bool(p95_latency_ms <= p95_budget_ms),
    }
    status = "pass" if all(checks.values()) else "fail"
    counts = {
        "num_cases": int(total_requests),
        "scored_cases": int(total_requests),
        "passed": int(successes),
    }

    payload = {
        "suite": "prod_load_smoke",
        "schema_version": "1.1",
        "status": status,
        "provider": provider,
        "counts": counts,
        "num_cases": int(counts["num_cases"]),
        "scored_cases": int(counts["scored_cases"]),
        "passed": int(counts["passed"]),
        "pass_rate": float(counts["passed"] / max(1, counts["scored_cases"])),
        "config": {
            "iters": int(total_requests),
            "timeout_sec": float(timeout_sec),
            "max_retries": int(max_retries),
            "p95_budget_ms": float(p95_budget_ms),
            "error_rate_budget": float(error_rate_budget),
        },
        "metrics": metrics,
        "checks": checks,
        "summary": {
            "counts": counts,
            "metrics": metrics,
            "checks": checks,
        },
        "samples": rows,
    }

    repo_root = Path(__file__).resolve().parents[1]
    out_path = (repo_root / args.output).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {out_path}")
    return 0 if status == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
