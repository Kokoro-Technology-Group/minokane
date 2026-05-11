#!/usr/bin/env bash
#
# Minokane local setup.
#
# - Ensures the `minokane` conda env exists (creates it on python 3.12 if not).
# - Installs Python deps into the env (backend/requirements.txt).
# - Installs npm deps (frontend/).
# - Seeds backend/.env from .env.example if missing.
#
# Hops in/out of backend/ and frontend/ via subshells, so when the script
# exits you're back at the project root regardless of where you ran it from.
#
# Usage:
#   ./setup.sh

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONDA_ENV="minokane"
PY_VERSION="3.12"

# ---------------------------------------------------------------------------
# Preflight
# ---------------------------------------------------------------------------

command -v conda >/dev/null 2>&1 || { echo "error: 'conda' not on PATH — install Miniconda first: https://docs.anaconda.com/miniconda/install/"; exit 1; }
command -v node  >/dev/null 2>&1 || { echo "error: 'node' not on PATH — install Node.js v22.12+: https://nodejs.org/"; exit 1; }
command -v npm   >/dev/null 2>&1 || { echo "error: 'npm' not on PATH (should ship with Node)"; exit 1; }

# shellcheck disable=SC1091
source "$(conda info --base)/etc/profile.d/conda.sh"

# ---------------------------------------------------------------------------
# Conda env
# ---------------------------------------------------------------------------

if conda env list | awk '{print $1}' | grep -qx "$CONDA_ENV"; then
  echo "[setup] conda env '$CONDA_ENV' already exists"
else
  echo "[setup] creating conda env '$CONDA_ENV' on python $PY_VERSION..."
  conda create -n "$CONDA_ENV" "python=$PY_VERSION" -y
fi

conda activate "$CONDA_ENV"

# ---------------------------------------------------------------------------
# Backend deps
# ---------------------------------------------------------------------------

echo "[setup] installing backend Python deps..."
(cd "$ROOT/backend" && pip install -r requirements.txt)

# ---------------------------------------------------------------------------
# Frontend deps
# ---------------------------------------------------------------------------

echo "[setup] installing frontend npm deps..."
(cd "$ROOT/frontend" && npm install)

# ---------------------------------------------------------------------------
# .env scaffolding
# ---------------------------------------------------------------------------

if [ ! -f "$ROOT/backend/.env" ]; then
  if [ -f "$ROOT/.env.example" ]; then
    cp "$ROOT/.env.example" "$ROOT/backend/.env"
    echo "[setup] seeded backend/.env from .env.example — edit it to set ANTHROPIC_API_KEY"
  else
    echo "[setup] warn: .env.example not found at project root; create backend/.env manually"
  fi
else
  echo "[setup] backend/.env already exists — leaving untouched"
fi

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------

cat <<EOF

[setup] done.

  Next steps:
    1. Make sure backend/.env has a real ANTHROPIC_API_KEY
    2. Activate the env:    conda activate $CONDA_ENV
    3. Start the stack:     ./dev.sh           (or ./dev.sh --tmux)

EOF
