#!/usr/bin/env bash
#
# Minokane — frontend-only dev server (Astro).
#
# The Ask / Think / Show flow now lives at "/" and is wired to the live backend,
# so it needs the API running too. Use ./run.sh (real LLMs) or ./test.sh
# (zero-cost mock) to launch backend + frontend together.
#
# This script starts ONLY the frontend — useful for pure UI/styling work; the
# Ask -> Think -> Show data flow will error without a backend.
#
# Usage:
#   ./testdraft.sh

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND="$ROOT/frontend"

command -v node >/dev/null 2>&1 || { echo "error: 'node' not on PATH"; exit 1; }

if [ ! -d "$FRONTEND/node_modules" ] || [ ! -d "$FRONTEND/node_modules/d3" ]; then
  echo "[testdraft] installing frontend deps (incl. d3)..."
  (cd "$FRONTEND" && npm install)
fi

echo "[testdraft] frontend-only (no backend) — bound to 0.0.0.0"
echo "[testdraft]   local:    http://localhost:4321/"
echo "[testdraft]   network:  http://$(ipconfig getifaddr en0 2>/dev/null || echo '<your-ip>'):4321/"
exec sh -c "cd '$FRONTEND' && npm run dev -- --host 0.0.0.0"
