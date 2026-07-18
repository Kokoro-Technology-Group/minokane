#!/usr/bin/env bash
#
# Minokane — testdraft launcher (FRONTEND ONLY).
#
# Rough-draft prototype of the Ask / Think / Show flow. No backend, no API key,
# fake data only. A separate person owns the backend + real data.
#
# Serves the Astro dev server and points you at /testdraft.
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

echo "[testdraft] frontend-only draft — bound to 0.0.0.0"
echo "[testdraft]   local:    http://localhost:4321/testdraft"
echo "[testdraft]   network:  http://$(ipconfig getifaddr en0 2>/dev/null || echo '<your-ip>'):4321/testdraft"
exec sh -c "cd '$FRONTEND' && npm run dev -- --host 0.0.0.0"
