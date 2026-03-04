#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROMPT_FILE="${1:-$ROOT_DIR/.codex/prompts/cycle-001.md}"
RUNS_DIR="$ROOT_DIR/.codex/runs"
STAMP="$(date +%Y%m%d-%H%M%S)"
OUT_FILE="$RUNS_DIR/swarm-${STAMP}.final.txt"
LOG_FILE="$RUNS_DIR/swarm-${STAMP}.log"

if [[ ! -f "$PROMPT_FILE" ]]; then
  echo "Prompt file not found: $PROMPT_FILE" >&2
  exit 1
fi

mkdir -p "$RUNS_DIR"

echo "Running Codex swarm in: $ROOT_DIR"
echo "Prompt file: $PROMPT_FILE"
echo "Final message: $OUT_FILE"
echo "Full log: $LOG_FILE"

codex exec \
  --cd "$ROOT_DIR" \
  --enable multi_agent \
  --sandbox workspace-write \
  --dangerously-bypass-approvals-and-sandbox \
  -o "$OUT_FILE" \
  - < "$PROMPT_FILE" | tee "$LOG_FILE"

echo
echo "Swarm run complete."
echo "Final message saved to: $OUT_FILE"
echo "Full log saved to: $LOG_FILE"
