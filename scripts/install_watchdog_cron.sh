#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$ROOT_DIR/.codex/runs/watchdog"
mkdir -p "$LOG_DIR"

CRON_MARKER="# moaa-prime-watchdog"
CRON_LINE="17 * * * * /bin/zsh -lc 'cd \"$ROOT_DIR\" && ./scripts/watchdog_cycle.sh >> \"$LOG_DIR/cron.log\" 2>&1' $CRON_MARKER"

CURRENT_CRON="$(crontab -l 2>/dev/null || true)"
CLEANED_CRON="$(printf "%s\n" "$CURRENT_CRON" | sed '/moaa-prime-watchdog/d')"

if [[ -n "$CLEANED_CRON" ]]; then
  NEW_CRON="${CLEANED_CRON}
${CRON_LINE}"
else
  NEW_CRON="$CRON_LINE"
fi

printf "%s\n" "$NEW_CRON" | crontab -

echo "Installed cron entry:"
crontab -l | grep 'moaa-prime-watchdog' || true
