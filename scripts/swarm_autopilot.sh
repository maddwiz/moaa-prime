#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNS_DIR="$ROOT_DIR/.codex/runs"
STATE_DIR="$RUNS_DIR/autopilot"
PID_FILE="$STATE_DIR/autopilot.pid"
STATUS_FILE="$STATE_DIR/status.env"
HEARTBEAT_FILE="$STATE_DIR/heartbeat.txt"
SUMMARY_FILE="$STATE_DIR/cycles.tsv"
DAEMON_LOG="$STATE_DIR/daemon.log"
STOP_REQUEST_FILE="$STATE_DIR/stop.requested"
ACTIVE_PROMPT_FILE="$STATE_DIR/active_prompt.md"

SWARM_RUNNER="$ROOT_DIR/scripts/run_swarm_cycle.sh"
DEFAULT_BASE_PROMPT="$ROOT_DIR/.codex/prompts/autopilot.md"
DEFAULT_FALLBACK_PROMPT="$ROOT_DIR/.codex/prompts/cycle-003-direct.md"

SLEEP_SECONDS="${SWARM_AUTOPILOT_SLEEP_SECONDS:-10}"
FULL_VALIDATE_EVERY="${SWARM_AUTOPILOT_FULL_VALIDATE_EVERY:-5}"
MAX_FAILURE_STREAK="${SWARM_AUTOPILOT_MAX_FAILURE_STREAK:-3}"
AUTOCOMMIT="${SWARM_AUTOPILOT_AUTOCOMMIT:-0}"
AUTOPUSH="${SWARM_AUTOPILOT_AUTOPUSH:-0}"
BRANCH_PREFIX="${SWARM_AUTOPILOT_BRANCH_PREFIX:-codex/}"
VALIDATE_MODE="${SWARM_AUTOPILOT_VALIDATE_MODE:-auto}" # auto|quick|full|none
SINGLE_CYCLE="${SWARM_AUTOPILOT_SINGLE_CYCLE:-0}"

usage() {
  cat <<'EOF'
Usage:
  scripts/swarm_autopilot.sh start [base_prompt] [fallback_prompt]
  scripts/swarm_autopilot.sh once [base_prompt] [fallback_prompt]
  scripts/swarm_autopilot.sh run [base_prompt] [fallback_prompt]   # internal foreground loop
  scripts/swarm_autopilot.sh status
  scripts/swarm_autopilot.sh stop
  scripts/swarm_autopilot.sh tail [lines]

Environment:
  SWARM_AUTOPILOT_SLEEP_SECONDS=10
  SWARM_AUTOPILOT_FULL_VALIDATE_EVERY=5
  SWARM_AUTOPILOT_MAX_FAILURE_STREAK=3
  SWARM_AUTOPILOT_VALIDATE_MODE=auto|quick|full|none
  SWARM_AUTOPILOT_AUTOCOMMIT=0|1
  SWARM_AUTOPILOT_AUTOPUSH=0|1
  SWARM_AUTOPILOT_BRANCH_PREFIX=codex/
EOF
}

timestamp() {
  date -u +"%Y-%m-%dT%H:%M:%SZ"
}

ensure_state_dir() {
  mkdir -p "$STATE_DIR"
  if [[ ! -f "$SUMMARY_FILE" ]]; then
    printf "started_at\tcycle\tstatus\tswarm_exit\tvalidate_exit\tauto_commit\tauto_push\tduration_sec\thead_before\thead_after\tprompt_source\n" > "$SUMMARY_FILE"
  fi
}

is_running() {
  if [[ ! -f "$PID_FILE" ]]; then
    return 1
  fi

  local pid
  pid="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [[ -z "$pid" ]]; then
    return 1
  fi

  if kill -0 "$pid" >/dev/null 2>&1; then
    return 0
  fi

  return 1
}

write_status() {
  local cycle="$1"
  local status="$2"
  local swarm_exit="$3"
  local validate_exit="$4"
  local fail_streak="$5"
  local prompt_source="$6"
  local head_before="$7"
  local head_after="$8"
  local duration="$9"

  cat > "$STATUS_FILE" <<EOF
updated_at=$(timestamp)
cycle=$cycle
status=$status
swarm_exit=$swarm_exit
validate_exit=$validate_exit
failure_streak=$fail_streak
prompt_source=$prompt_source
head_before=$head_before
head_after=$head_after
duration_sec=$duration
EOF
}

guard_branch_prefix() {
  local branch
  branch="$(git -C "$ROOT_DIR" branch --show-current)"
  if [[ -z "$branch" ]]; then
    echo "Refusing to run: detached HEAD." >&2
    exit 1
  fi

  if [[ "$branch" != "$BRANCH_PREFIX"* ]]; then
    echo "Refusing to run on branch '$branch' (required prefix: '$BRANCH_PREFIX')." >&2
    exit 1
  fi
}

resolve_pytest_bin() {
  if [[ -x "$ROOT_DIR/.venv/bin/pytest" ]]; then
    echo "$ROOT_DIR/.venv/bin/pytest"
    return
  fi
  echo "pytest"
}

resolve_python_bin() {
  if [[ -x "$ROOT_DIR/.venv/bin/python" ]]; then
    echo "$ROOT_DIR/.venv/bin/python"
    return
  fi
  echo "python"
}

append_cycle_prompt() {
  local base_prompt="$1"
  local fallback_prompt="$2"
  local cycle="$3"
  local failure_streak="$4"
  local chosen_prompt="$base_prompt"

  if (( failure_streak >= MAX_FAILURE_STREAK )) && [[ -f "$fallback_prompt" ]]; then
    chosen_prompt="$fallback_prompt"
  fi

  local branch head dirty_count
  branch="$(git -C "$ROOT_DIR" branch --show-current)"
  head="$(git -C "$ROOT_DIR" rev-parse --short HEAD)"
  dirty_count="$(git -C "$ROOT_DIR" status --porcelain | wc -l | tr -d ' ')"

  {
    echo "Autopilot runtime context:"
    echo "- UTC timestamp: $(timestamp)"
    echo "- Cycle index: $cycle"
    echo "- Branch: $branch"
    echo "- HEAD: $head"
    echo "- Dirty file count before cycle: $dirty_count"
    echo "- Failure streak entering cycle: $failure_streak"
    echo
    cat "$chosen_prompt"
    cat <<'EOF'

Hard execution requirements for this cycle:
- Make concrete implementation progress; do not stop at planning.
- Prefer Codex multi-agent spawning when available.
- Run tests and relevant scripts before finishing the cycle.
- Update continuity docs when behavior changes.
- Commit completed work with a clear message.
EOF
  } > "$ACTIVE_PROMPT_FILE"

  echo "$chosen_prompt"
}

run_validation() {
  local cycle="$1"
  local pytest_bin python_bin mode
  pytest_bin="$(resolve_pytest_bin)"
  python_bin="$(resolve_python_bin)"
  mode="$VALIDATE_MODE"

  if [[ "$mode" == "auto" ]]; then
    if (( FULL_VALIDATE_EVERY > 0 && cycle % FULL_VALIDATE_EVERY == 0 )); then
      mode="full"
    else
      mode="quick"
    fi
  fi

  case "$mode" in
    none)
      return 0
      ;;
    quick)
      "$pytest_bin" -q
      ;;
    full)
      "$pytest_bin" -q
      "$python_bin" "$ROOT_DIR/scripts/demo_run.py"
      "$python_bin" "$ROOT_DIR/scripts/bench_run.py"
      "$python_bin" "$ROOT_DIR/scripts/eval_run.py"
      "$python_bin" "$ROOT_DIR/scripts/eval_compare.py"
      "$python_bin" "$ROOT_DIR/scripts/train_router.py"
      "$python_bin" "$ROOT_DIR/scripts/eval_router.py"
      ;;
    *)
      echo "Unsupported SWARM_AUTOPILOT_VALIDATE_MODE: $mode" >&2
      return 2
      ;;
  esac
}

maybe_autocommit_and_push() {
  local cycle="$1"
  local commit_status="skipped"
  local push_status="skipped"

  if [[ "$AUTOCOMMIT" == "1" ]]; then
    if [[ -n "$(git -C "$ROOT_DIR" status --porcelain)" ]]; then
      git -C "$ROOT_DIR" add -A
      git -C "$ROOT_DIR" commit -m "swarm: autopilot cycle ${cycle} checkpoint"
      commit_status="ok"
    else
      commit_status="no_changes"
    fi

    if [[ "$AUTOPUSH" == "1" ]] && [[ "$commit_status" == "ok" ]]; then
      if git -C "$ROOT_DIR" push; then
        push_status="ok"
      else
        push_status="failed"
      fi
    fi
  fi

  echo "$commit_status|$push_status"
}

run_loop() {
  local base_prompt="${1:-$DEFAULT_BASE_PROMPT}"
  local fallback_prompt="${2:-$DEFAULT_FALLBACK_PROMPT}"
  local single_cycle="${3:-$SINGLE_CYCLE}"

  cd "$ROOT_DIR"
  ensure_state_dir
  guard_branch_prefix

  if [[ ! -x "$SWARM_RUNNER" ]]; then
    echo "Missing executable swarm runner: $SWARM_RUNNER" >&2
    exit 1
  fi

  if [[ ! -f "$base_prompt" ]]; then
    echo "Base prompt not found: $base_prompt" >&2
    exit 1
  fi

  rm -f "$STOP_REQUEST_FILE"
  local cycle=0
  local failure_streak=0

  echo "Autopilot loop started at $(timestamp)"
  echo "Base prompt: $base_prompt"
  echo "Fallback prompt: $fallback_prompt"
  echo "State dir: $STATE_DIR"

  while true; do
    cycle=$((cycle + 1))
    printf "%s\n" "$(timestamp)" > "$HEARTBEAT_FILE"

    local started_at started_epoch prompt_source head_before head_after swarm_exit validate_exit status duration
    local auto_pair auto_commit auto_push
    started_at="$(timestamp)"
    started_epoch="$(date +%s)"
    head_before="$(git -C "$ROOT_DIR" rev-parse HEAD)"
    prompt_source="$(append_cycle_prompt "$base_prompt" "$fallback_prompt" "$cycle" "$failure_streak")"

    echo "[$started_at] Cycle $cycle starting (failure_streak=$failure_streak, prompt_source=$prompt_source)"

    swarm_exit=0
    if ! "$SWARM_RUNNER" "$ACTIVE_PROMPT_FILE"; then
      swarm_exit=$?
    fi

    validate_exit=0
    if [[ "$swarm_exit" -eq 0 ]]; then
      if ! run_validation "$cycle"; then
        validate_exit=$?
      fi
    else
      validate_exit=99
    fi

    auto_commit="skipped"
    auto_push="skipped"
    if [[ "$swarm_exit" -eq 0 && "$validate_exit" -eq 0 ]]; then
      auto_pair="$(maybe_autocommit_and_push "$cycle")"
      auto_commit="${auto_pair%%|*}"
      auto_push="${auto_pair##*|}"
      status="ok"
      failure_streak=0
    else
      status="failed"
      failure_streak=$((failure_streak + 1))
    fi

    head_after="$(git -C "$ROOT_DIR" rev-parse HEAD)"
    duration="$(( $(date +%s) - started_epoch ))"

    write_status "$cycle" "$status" "$swarm_exit" "$validate_exit" "$failure_streak" "$prompt_source" "$head_before" "$head_after" "$duration"

    printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" \
      "$started_at" "$cycle" "$status" "$swarm_exit" "$validate_exit" "$auto_commit" "$auto_push" "$duration" "$head_before" "$head_after" "$prompt_source" >> "$SUMMARY_FILE"

    echo "[$(timestamp)] Cycle $cycle finished: status=$status swarm_exit=$swarm_exit validate_exit=$validate_exit"

    if [[ "$single_cycle" == "1" ]]; then
      echo "Single-cycle mode enabled, exiting loop."
      break
    fi

    if [[ -f "$STOP_REQUEST_FILE" ]]; then
      echo "Stop requested file found at $STOP_REQUEST_FILE; exiting loop."
      rm -f "$STOP_REQUEST_FILE"
      break
    fi

    sleep "$SLEEP_SECONDS"
  done
}

start_daemon() {
  local base_prompt="${1:-$DEFAULT_BASE_PROMPT}"
  local fallback_prompt="${2:-$DEFAULT_FALLBACK_PROMPT}"

  ensure_state_dir
  guard_branch_prefix

  if [[ ! -f "$base_prompt" ]]; then
    echo "Base prompt not found: $base_prompt" >&2
    exit 1
  fi

  if is_running; then
    echo "Autopilot already running (pid $(cat "$PID_FILE"))."
    exit 0
  fi

  rm -f "$STOP_REQUEST_FILE"
  nohup "$0" run "$base_prompt" "$fallback_prompt" >> "$DAEMON_LOG" 2>&1 &
  local pid=$!
  echo "$pid" > "$PID_FILE"

  echo "Autopilot started."
  echo "PID: $pid"
  echo "Daemon log: $DAEMON_LOG"
}

stop_daemon() {
  ensure_state_dir

  if ! is_running; then
    rm -f "$PID_FILE"
    echo "Autopilot is not running."
    exit 0
  fi

  local pid
  pid="$(cat "$PID_FILE")"
  touch "$STOP_REQUEST_FILE"
  kill "$pid" >/dev/null 2>&1 || true

  for _ in {1..20}; do
    if ! kill -0 "$pid" >/dev/null 2>&1; then
      break
    fi
    sleep 0.5
  done

  if kill -0 "$pid" >/dev/null 2>&1; then
    kill -9 "$pid" >/dev/null 2>&1 || true
  fi

  rm -f "$PID_FILE" "$STOP_REQUEST_FILE"
  echo "Autopilot stopped."
}

show_status() {
  ensure_state_dir

  if is_running; then
    echo "status=running"
    echo "pid=$(cat "$PID_FILE")"
  else
    echo "status=stopped"
  fi

  if [[ -f "$HEARTBEAT_FILE" ]]; then
    echo "heartbeat=$(cat "$HEARTBEAT_FILE")"
  fi

  if [[ -f "$STATUS_FILE" ]]; then
    echo
    cat "$STATUS_FILE"
  fi

  if [[ -f "$SUMMARY_FILE" ]]; then
    echo
    echo "recent_cycles:"
    tail -n 6 "$SUMMARY_FILE"
  fi
}

tail_daemon_log() {
  local lines="${1:-80}"
  ensure_state_dir
  touch "$DAEMON_LOG"
  tail -n "$lines" -f "$DAEMON_LOG"
}

cmd="${1:-status}"
case "$cmd" in
  start)
    start_daemon "${2:-$DEFAULT_BASE_PROMPT}" "${3:-$DEFAULT_FALLBACK_PROMPT}"
    ;;
  once)
    run_loop "${2:-$DEFAULT_BASE_PROMPT}" "${3:-$DEFAULT_FALLBACK_PROMPT}" "1"
    ;;
  run)
    run_loop "${2:-$DEFAULT_BASE_PROMPT}" "${3:-$DEFAULT_FALLBACK_PROMPT}"
    ;;
  status)
    show_status
    ;;
  stop)
    stop_daemon
    ;;
  tail)
    tail_daemon_log "${2:-80}"
    ;;
  help|-h|--help)
    usage
    ;;
  *)
    usage
    exit 1
    ;;
esac
