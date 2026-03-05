from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from pathlib import Path
from typing import Any, Callable

# Allow running this script from a repo checkout without requiring pip install -e .
_SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if _SRC_DIR.exists() and str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from moaa_prime.core.app import MoAAPrime
from moaa_prime.llm.factory import make_llm_from_env


def _run_with_timeout(
    fn: Callable[[], dict[str, Any]],
    *,
    timeout_sec: float,
    timeout_message: str,
) -> dict[str, Any]:
    timeout = max(1.0, float(timeout_sec))
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(fn)
        try:
            return dict(future.result(timeout=timeout))
        except FutureTimeoutError:
            return {"ok": False, "error": timeout_message, "timeout_sec": timeout}
        except Exception as exc:  # pragma: no cover - defensive
            return {"ok": False, "error": str(exc)}


def _check_python_version() -> dict[str, Any]:
    version = {
        "major": int(sys.version_info.major),
        "minor": int(sys.version_info.minor),
        "micro": int(sys.version_info.micro),
    }
    ok = (version["major"], version["minor"]) >= (3, 10)
    return {
        "ok": bool(ok),
        "version": version,
        "required": {"major": 3, "minor": 10},
    }


def _check_provider_env() -> dict[str, Any]:
    provider = (os.getenv("MOAA_LLM_PROVIDER") or "stub").strip().lower()
    supported = {"stub", "ollama"}
    return {
        "ok": bool(provider in supported),
        "provider": provider,
        "supported_providers": sorted(supported),
        "ollama_host": (os.getenv("MOAA_OLLAMA_HOST") or "http://127.0.0.1:11434"),
        "ollama_model": (os.getenv("MOAA_OLLAMA_MODEL") or "llama3.1:8b-instruct"),
    }


def _check_provider_wiring() -> dict[str, Any]:
    provider = (os.getenv("MOAA_LLM_PROVIDER") or "stub").strip().lower()
    client = make_llm_from_env()
    details: dict[str, Any] = {
        "provider": provider,
        "client_class": type(client).__name__,
    }
    try:
        response = client.generate("preflight ping")
    except Exception as exc:
        details["error"] = str(exc)
        return {"ok": False, **details}

    details.update(
        {
            "model": str(getattr(response, "model", "")),
            "response_non_empty": bool(str(getattr(response, "text", "")).strip()),
        }
    )
    for attr in ("request_timeout_sec", "max_retries", "retry_backoff_sec"):
        if hasattr(client, attr):
            details[attr] = getattr(client, attr)
    return {"ok": bool(details["response_non_empty"]), **details}


def _check_reports_fs(output_path: Path) -> dict[str, Any]:
    reports_dir = output_path.parent
    reports_dir.mkdir(parents=True, exist_ok=True)

    probe = reports_dir / ".preflight_write_probe.tmp"
    probe.write_text("ok", encoding="utf-8")
    probe.unlink(missing_ok=True)

    return {
        "ok": True,
        "reports_dir": str(reports_dir),
        "output_path": str(output_path),
        "reports_dir_exists": reports_dir.exists(),
        "reports_dir_writable": True,
    }


def _check_cli_health(repo_root: Path, *, timeout_sec: float) -> dict[str, Any]:
    cmd = [sys.executable, "-m", "moaa_prime", "--help"]
    try:
        run = subprocess.run(
            cmd,
            cwd=str(repo_root),
            check=False,
            capture_output=True,
            text=True,
            timeout=max(1.0, float(timeout_sec)),
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "cli --help timed out", "timeout_sec": float(timeout_sec)}

    stdout = (run.stdout or "").strip()
    stderr = (run.stderr or "").strip()
    return {
        "ok": bool(run.returncode == 0 and "usage" in stdout.lower()),
        "exit_code": int(run.returncode),
        "stdout_has_usage": bool("usage" in stdout.lower()),
        "stderr_tail": stderr[-240:],
    }


def _check_runtime_smoke() -> dict[str, Any]:
    app = MoAAPrime(mode="v3", seed=23)
    out = app.run_once("Solve 2x + 3 = 7. Return only x.", task_id="preflight-runtime", mode="v3")
    decision = out.get("decision", {}) if isinstance(out, dict) else {}
    oracle = out.get("oracle", {}) if isinstance(out, dict) else {}
    return {
        "ok": bool(isinstance(decision, dict) and isinstance(oracle, dict) and "agent" in decision),
        "decision_agent": str((decision or {}).get("agent", "")),
        "oracle_score": float((oracle or {}).get("score", 0.0)),
    }


def _run_check(name: str, fn: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    started = time.perf_counter()
    payload: dict[str, Any]
    status = "pass"
    try:
        payload = dict(fn())
        status = "pass" if bool(payload.get("ok", False)) else "fail"
    except Exception as exc:  # pragma: no cover - defensive
        payload = {"ok": False, "error": str(exc)}
        status = "fail"
    ended = time.perf_counter()
    payload.pop("ok", None)
    return {
        "name": name,
        "status": status,
        "duration_ms": float(round((ended - started) * 1000.0, 3)),
        "details": payload,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run production preflight checks and emit machine-readable JSON.")
    parser.add_argument("--output", default="reports/preflight_prod.json")
    parser.add_argument("--cli-timeout-sec", type=float, default=20.0)
    parser.add_argument("--runtime-timeout-sec", type=float, default=25.0)
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    output_path = (repo_root / args.output).resolve()

    checks = [
        _run_check("python_version", _check_python_version),
        _run_check("provider_env", _check_provider_env),
        _run_check("provider_wiring", _check_provider_wiring),
        _run_check("reports_filesystem", lambda: _check_reports_fs(output_path)),
        _run_check("cli_health", lambda: _check_cli_health(repo_root, timeout_sec=float(args.cli_timeout_sec))),
        _run_check(
            "runtime_smoke",
            lambda: _run_with_timeout(
                _check_runtime_smoke,
                timeout_sec=float(args.runtime_timeout_sec),
                timeout_message="runtime smoke timed out",
            ),
        ),
    ]

    passed = int(sum(1 for item in checks if item.get("status") == "pass"))
    failed = int(sum(1 for item in checks if item.get("status") != "pass"))
    status = "pass" if failed == 0 else "fail"
    counts = {
        "num_cases": int(len(checks)),
        "scored_cases": int(len(checks)),
        "passed": int(passed),
    }

    payload = {
        "suite": "prod_preflight",
        "schema_version": "1.1",
        "status": status,
        "counts": counts,
        "num_cases": int(counts["num_cases"]),
        "scored_cases": int(counts["scored_cases"]),
        "passed": int(counts["passed"]),
        "pass_rate": float(counts["passed"] / max(1, counts["scored_cases"])),
        "summary": {
            "counts": counts,
            "metrics": {
                "total_checks": int(len(checks)),
                "passed_checks": int(passed),
                "failed_checks": int(failed),
                "status": status,
            },
        },
        "checks": checks,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {output_path}")
    return 0 if status == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
