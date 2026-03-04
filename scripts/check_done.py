from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _json_path_get(doc: Any, path: str) -> Any:
    current = doc
    for raw_part in path.split("."):
        part = raw_part.strip()
        if part == "":
            raise KeyError("empty path segment")
        if isinstance(current, list):
            idx = int(part)
            current = current[idx]
            continue
        if isinstance(current, dict):
            if part not in current:
                raise KeyError(part)
            current = current[part]
            continue
        raise KeyError(part)
    return current


def _compare(actual: Any, op: str, expected: Any) -> bool:
    if op == "eq":
        return actual == expected
    if op == "ne":
        return actual != expected

    actual_f = float(actual)
    expected_f = float(expected)
    if op == "ge":
        return actual_f >= expected_f
    if op == "gt":
        return actual_f > expected_f
    if op == "le":
        return actual_f <= expected_f
    if op == "lt":
        return actual_f < expected_f
    raise ValueError(f"unsupported operator: {op}")


def _git_is_clean(repo_root: Path) -> bool:
    out = subprocess.run(
        ["git", "-C", str(repo_root), "status", "--porcelain"],
        check=True,
        capture_output=True,
        text=True,
    )
    return out.stdout.strip() == ""


@dataclass
class CheckResult:
    name: str
    passed: bool
    message: str
    actual: Any = None
    expected: Any = None
    operator: str = ""
    file: str = ""
    path: str = ""
    command: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "passed": self.passed,
            "message": self.message,
            "actual": self.actual,
            "expected": self.expected,
            "operator": self.operator,
            "file": self.file,
            "path": self.path,
            "command": self.command,
        }


def evaluate(criteria_path: Path, repo_root: Path) -> Dict[str, Any]:
    criteria = _read_json(criteria_path)

    required_files = [Path(p) for p in criteria.get("required_files", [])]
    file_checks = criteria.get("file_checks", [])
    command_checks = criteria.get("command_checks", [])
    metric_checks = criteria.get("checks", [])
    require_clean_worktree = bool(criteria.get("require_clean_worktree", False))

    results: List[CheckResult] = []
    json_cache: Dict[Path, Any] = {}

    for rel in required_files:
        target = repo_root / rel
        ok = target.exists()
        msg = "exists" if ok else "missing"
        results.append(
            CheckResult(
                name=f"file:{rel}",
                passed=ok,
                message=msg,
                file=str(rel),
            )
        )

    for idx, check in enumerate(file_checks):
        name = str(check.get("name") or f"file_check_{idx + 1}")
        file_rel = Path(str(check["file"]))
        full = repo_root / file_rel
        min_bytes = int(check.get("min_bytes", 0))
        contains = check.get("contains")

        if not full.exists():
            results.append(
                CheckResult(
                    name=name,
                    passed=False,
                    message="source file missing",
                    expected={"exists": True, "min_bytes": min_bytes, "contains": contains},
                    file=str(file_rel),
                )
            )
            continue

        try:
            text = _read_text(full)
            size = len(text.encode("utf-8"))
            passed = size >= min_bytes
            msg = "ok" if passed else f"size {size} < min_bytes {min_bytes}"

            if passed and contains is not None:
                if isinstance(contains, list):
                    missing = [str(s) for s in contains if str(s) not in text]
                    if missing:
                        passed = False
                        msg = f"missing required text: {missing}"
                else:
                    needle = str(contains)
                    if needle not in text:
                        passed = False
                        msg = f"missing required text: {needle}"

            results.append(
                CheckResult(
                    name=name,
                    passed=passed,
                    message=msg,
                    actual={"bytes": size},
                    expected={"min_bytes": min_bytes, "contains": contains},
                    file=str(file_rel),
                )
            )
        except Exception as exc:  # pragma: no cover - defensive path
            results.append(
                CheckResult(
                    name=name,
                    passed=False,
                    message=f"evaluation error: {exc}",
                    expected={"min_bytes": min_bytes, "contains": contains},
                    file=str(file_rel),
                )
            )

    if require_clean_worktree:
        clean = _git_is_clean(repo_root)
        results.append(
            CheckResult(
                name="git_clean_worktree",
                passed=clean,
                message="clean" if clean else "dirty",
            )
        )

    for idx, check in enumerate(metric_checks):
        name = str(check.get("name") or f"check_{idx + 1}")
        file_rel = Path(str(check["file"]))
        path = str(check["path"])
        op = str(check["op"]).strip().lower()
        expected = check["value"]
        full = repo_root / file_rel

        if not full.exists():
            results.append(
                CheckResult(
                    name=name,
                    passed=False,
                    message="source file missing",
                    expected=expected,
                    operator=op,
                    file=str(file_rel),
                    path=path,
                )
            )
            continue

        try:
            if full not in json_cache:
                json_cache[full] = _read_json(full)
            actual = _json_path_get(json_cache[full], path)
            passed = _compare(actual, op, expected)
            results.append(
                CheckResult(
                    name=name,
                    passed=passed,
                    message="ok" if passed else "threshold not met",
                    actual=actual,
                    expected=expected,
                    operator=op,
                    file=str(file_rel),
                    path=path,
                )
            )
        except Exception as exc:  # pragma: no cover - defensive path
            results.append(
                CheckResult(
                    name=name,
                    passed=False,
                    message=f"evaluation error: {exc}",
                    expected=expected,
                    operator=op,
                    file=str(file_rel),
                    path=path,
                )
            )

    for idx, check in enumerate(command_checks):
        name = str(check.get("name") or f"command_check_{idx + 1}")
        cmd = str(check["cmd"])
        timeout_sec = int(check.get("timeout_sec", 600))
        expected_exit = int(check.get("expected_exit", 0))

        try:
            run = subprocess.run(
                cmd,
                shell=True,
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                timeout=timeout_sec,
            )
            passed = run.returncode == expected_exit
            stderr_tail = (run.stderr or "").strip()[-500:]
            stdout_tail = (run.stdout or "").strip()[-500:]
            msg = "ok" if passed else f"exit {run.returncode} != expected {expected_exit}"
            if not passed:
                detail = stderr_tail or stdout_tail
                if detail:
                    msg = f"{msg}; detail={detail}"

            results.append(
                CheckResult(
                    name=name,
                    passed=passed,
                    message=msg,
                    actual={"exit_code": run.returncode},
                    expected={"expected_exit": expected_exit},
                    command=cmd,
                )
            )
        except subprocess.TimeoutExpired:
            results.append(
                CheckResult(
                    name=name,
                    passed=False,
                    message=f"command timed out after {timeout_sec}s",
                    expected={"expected_exit": expected_exit},
                    command=cmd,
                )
            )
        except Exception as exc:  # pragma: no cover - defensive path
            results.append(
                CheckResult(
                    name=name,
                    passed=False,
                    message=f"command failed to run: {exc}",
                    expected={"expected_exit": expected_exit},
                    command=cmd,
                )
            )

    done = all(item.passed for item in results) if results else False
    failed = [item.name for item in results if not item.passed]

    return {
        "checked_at": _utc_now_iso(),
        "criteria_path": str(criteria_path),
        "done": done,
        "failed": failed,
        "results": [item.to_dict() for item in results],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate MoAA done criteria.")
    parser.add_argument("--criteria", default=".codex/done_criteria.json")
    parser.add_argument("--report", default=".codex/runs/autopilot/done_check.json")
    parser.add_argument("--repo-root", default=".")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    criteria_path = (repo_root / args.criteria).resolve()
    report_path = (repo_root / args.report).resolve()

    if not criteria_path.exists():
        print(f"[done-check] criteria file not found: {criteria_path}")
        return 3

    try:
        payload = evaluate(criteria_path=criteria_path, repo_root=repo_root)
    except Exception as exc:  # pragma: no cover - defensive path
        print(f"[done-check] fatal error: {exc}")
        return 4

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    if payload["done"]:
        print(f"[done-check] DONE criteria met. Report: {report_path}")
        return 0

    print("[done-check] NOT done yet.")
    if payload["failed"]:
        print(f"[done-check] Failed checks: {', '.join(payload['failed'])}")
    print(f"[done-check] Report: {report_path}")
    return 10


if __name__ == "__main__":
    raise SystemExit(main())
