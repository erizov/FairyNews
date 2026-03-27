#!/usr/bin/env bash
# Start FairyNews MVP in the foreground (Ctrl+C to stop).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PORT="${PORT:-8765}"
PY="python3"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PY="$ROOT/.venv/bin/python"
fi
exec "$PY" -m uvicorn app.main:app --host 127.0.0.1 --port "$PORT"
