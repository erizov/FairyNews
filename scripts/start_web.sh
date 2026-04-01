#!/usr/bin/env bash
# Start FairyNews MVP in the foreground (Ctrl+C to stop).
# Optional: UVICORN_RELOAD=1 for --reload.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PORT="${PORT:-8765}"
PY="python3"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PY="$ROOT/.venv/bin/python"
fi
extra=()
if [[ "${UVICORN_RELOAD:-}" == "1" ]]; then
  extra+=(--reload)
fi
exec "$PY" -m uvicorn app.main:app --host 127.0.0.1 --port "$PORT" "${extra[@]}"
