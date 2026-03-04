#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$ROOT_DIR/.codex/runs/watchdog"
mkdir -p "$LOG_DIR"

BASE_BRANCH="${MOAA_WATCHDOG_BASE_BRANCH:-main}"
FIX_BRANCH_PREFIX="${MOAA_WATCHDOG_FIX_BRANCH_PREFIX:-codex/watchdog-}"
PROMPT_FILE="${MOAA_WATCHDOG_PROMPT:-$ROOT_DIR/.codex/prompts/watchdog-regression.md}"

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
LOG_FILE="$LOG_DIR/watchdog_${STAMP}.log"

exec > >(tee -a "$LOG_FILE") 2>&1

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] watchdog start"
echo "root=$ROOT_DIR"
echo "base_branch=$BASE_BRANCH"

if [[ ! -f "$PROMPT_FILE" ]]; then
  PROMPT_FILE="$ROOT_DIR/.codex/prompts/autopilot.md"
fi

echo "prompt_file=$PROMPT_FILE"

resolve_pytest() {
  if [[ -x "$ROOT_DIR/.venv/bin/pytest" ]]; then
    echo "$ROOT_DIR/.venv/bin/pytest"
  else
    echo "pytest"
  fi
}

resolve_python() {
  if [[ -x "$ROOT_DIR/.venv/bin/python" ]]; then
    echo "$ROOT_DIR/.venv/bin/python"
  else
    echo "python"
  fi
}

run_gate_checks() {
  local pytest_bin python_bin
  pytest_bin="$(resolve_pytest)"
  python_bin="$(resolve_python)"

  "$pytest_bin" -q
  "$python_bin" "$ROOT_DIR/scripts/eval_matrix.py"
  if "$python_bin" "$ROOT_DIR/scripts/check_done.py" --criteria "$ROOT_DIR/.codex/done_criteria.json" --report "$ROOT_DIR/.codex/runs/watchdog/last_done_check.json"; then
    return 0
  fi

  local only_dirty
  only_dirty="$("$python_bin" - <<'PY'
import json
from pathlib import Path

report_path = Path(".codex/runs/watchdog/last_done_check.json")
if not report_path.exists():
    print("0")
    raise SystemExit(0)

payload = json.loads(report_path.read_text())
failed = payload.get("failed", [])
print("1" if failed == ["git_clean_worktree"] else "0")
PY
)"

  # The watchdog itself regenerates reports. If that is the only failing gate,
  # restore generated artifacts and treat the run as healthy.
  if [[ "$only_dirty" == "1" ]]; then
    git -C "$ROOT_DIR" restore --worktree --staged reports || true
    return 0
  fi

  return 1
}

cd "$ROOT_DIR"

git fetch origin --prune

git checkout "$BASE_BRANCH"
git pull --ff-only origin "$BASE_BRANCH"

# Do not attempt auto-fixes when local edits are present.
if [[ -n "$(git status --porcelain)" ]]; then
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] watchdog skipped: dirty working tree on $BASE_BRANCH"
  exit 0
fi

if run_gate_checks; then
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] watchdog healthy: no regression"
  exit 0
fi

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] regression detected; starting fix swarm"

FIX_BRANCH="${FIX_BRANCH_PREFIX}${STAMP}"
git checkout -b "$FIX_BRANCH"

SWARM_AUTOPILOT_AUTOCOMMIT=1 \
SWARM_AUTOPILOT_AUTOPUSH=1 \
SWARM_AUTOPILOT_VALIDATE_MODE=full \
SWARM_AUTOPILOT_DONE_CHECK_ENABLED=1 \
SWARM_AUTOPILOT_BRANCH_PREFIX="codex/" \
SWARM_AUTOPILOT_SINGLE_CYCLE=1 \
"$ROOT_DIR/scripts/swarm_autopilot.sh" once "$PROMPT_FILE"

# Ensure branch is pushed even if no commit was made by autopilot.
if ! git rev-parse --abbrev-ref --symbolic-full-name "@{u}" >/dev/null 2>&1; then
  git push -u origin "$FIX_BRANCH"
else
  git push || true
fi

# Re-run checks after fix attempt for visibility in logs.
if run_gate_checks; then
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] fix cycle complete: checks passing"
else
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] fix cycle ended but checks still failing"
  exit 1
fi
