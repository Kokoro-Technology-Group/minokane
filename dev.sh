#!/usr/bin/env bash
#
# Minokane local dev launcher.
#
# Usage:
#   ./dev.sh           # bash with prefixed interleaved logs
#   ./dev.sh --tmux    # tmux split-pane variant (requires tmux)
#
# CTRL+C tears down both processes (uses process-group kill).

set -euo pipefail
set -m  # job control: each "&" launches into its own process group

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONDA_ENV="minokane"

# ---------------------------------------------------------------------------
# Preflight
# ---------------------------------------------------------------------------

command -v conda >/dev/null 2>&1 || { echo "error: 'conda' not on PATH"; exit 1; }
command -v node  >/dev/null 2>&1 || { echo "error: 'node' not on PATH"; exit 1; }

if [ ! -f "$ROOT/backend/.env" ]; then
  echo "warn: $ROOT/backend/.env not found — backend may fail without ANTHROPIC_API_KEY"
fi

if [ ! -d "$ROOT/frontend/node_modules" ]; then
  echo "info: installing frontend dependencies..."
  (cd "$ROOT/frontend" && npm install)
fi

# ---------------------------------------------------------------------------
# tmux branch
# ---------------------------------------------------------------------------

if [ "${1:-}" = "--tmux" ]; then
  command -v tmux >/dev/null 2>&1 || { echo "error: 'tmux' not on PATH"; exit 1; }
  SESSION="minokane"

  if tmux has-session -t "$SESSION" 2>/dev/null; then
    echo "tmux session '$SESSION' already exists — attaching"
    exec tmux attach -t "$SESSION"
  fi

  tmux new-session  -d -s "$SESSION" \
    "bash -ic 'cd \"$ROOT/backend\" && conda activate $CONDA_ENV && uvicorn app.main:app --reload --port 8000; exec bash'"
  tmux split-window -v -t "$SESSION" \
    "bash -ic 'cd \"$ROOT/frontend\" && npm run dev; exec bash'"
  tmux select-pane  -t "$SESSION":0.0
  exec tmux attach  -t "$SESSION"
fi

# ---------------------------------------------------------------------------
# Default branch: plain bash, prefixed interleaved logs, process-group kill
# ---------------------------------------------------------------------------

# shellcheck disable=SC1091
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate "$CONDA_ENV"

echo "[dev.sh] starting backend on :8000 and frontend on :4321 — CTRL+C to stop"

(cd "$ROOT/backend"  && exec uvicorn app.main:app --reload --port 8000) 2>&1 \
  | awk '{print "[backend] " $0; fflush()}' &
BACK=$!

(cd "$ROOT/frontend" && exec npm run dev) 2>&1 \
  | awk '{print "[frontend] " $0; fflush()}' &
FRONT=$!

shutdown() {
  trap - INT TERM
  echo
  echo "[dev.sh] shutting down..."
  kill -TERM "-$BACK" "-$FRONT" 2>/dev/null || true
  wait 2>/dev/null || true
  exit 0
}
trap shutdown INT TERM

# Exit as soon as either process dies (don't auto-restart — surface failures).
wait -n "$BACK" "$FRONT" || true
echo "[dev.sh] one process exited — tearing down the other"
kill -TERM "-$BACK" "-$FRONT" 2>/dev/null || true
wait 2>/dev/null || true
exit 1
