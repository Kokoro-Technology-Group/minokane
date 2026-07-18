#!/usr/bin/env bash
#
# Minokane — normal launch (real Anthropic LLMs).
#
# Thin wrapper over dev.sh. Requires backend/.env with a valid ANTHROPIC_API_KEY.
#
# Usage:
#   ./run.sh            # bash, interleaved logs
#   ./run.sh --tmux     # tmux split-pane variant
#
# See ./test.sh for the zero-cost lorem-ipsum mock variant.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$ROOT/dev.sh" "$@"
