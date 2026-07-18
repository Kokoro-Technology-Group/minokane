#!/usr/bin/env bash
#
# Minokane — mock launch (offline lorem ipsum, ZERO Anthropic API calls).
#
# Same full stack as run.sh (backend + frontend), but sets MOCK_LLM=1 so every
# persona returns schema-valid lorem ipsum instead of calling the LLM. No
# ANTHROPIC_API_KEY required. Use to click through the whole app, exercise the
# LangGraph + storage + frontend wiring, and run end-to-end smoke checks without
# spending tokens.
#
# Env vars override .env in pydantic-settings, so MOCK_LLM exported here wins
# even if backend/.env sets mock_llm=false.
#
# Usage:
#   ./test.sh           # bash, interleaved logs
#   ./test.sh --tmux    # tmux split-pane variant

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

export MOCK_LLM=1

echo "[test.sh] MOCK_LLM=1 — offline lorem ipsum mode, no Anthropic API calls"
exec "$ROOT/dev.sh" "$@"
