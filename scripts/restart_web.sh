#!/usr/bin/env bash
# Stop then start FairyNews on PORT (default 8765). Pass-through env: PORT,
# UVICORN_RELOAD=1 for --reload on start (see start_web.sh).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PORT="${PORT:-8765}"
"$ROOT/scripts/stop_web.sh"
sleep 1
exec "$ROOT/scripts/start_web.sh"
