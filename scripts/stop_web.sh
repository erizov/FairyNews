#!/usr/bin/env bash
# Kill whatever is listening on PORT (default 8765). Linux/macOS.
set -euo pipefail
PORT="${PORT:-8765}"
if command -v fuser >/dev/null 2>&1; then
  fuser -k "${PORT}/tcp" 2>/dev/null && echo "Stopped listeners on tcp/$PORT." \
    || echo "No listener on tcp/$PORT."
elif command -v lsof >/dev/null 2>&1; then
  pids="$(lsof -t -i ":${PORT}" -sTCP:LISTEN 2>/dev/null || true)"
  if [[ -n "${pids:-}" ]]; then
    kill $pids
    echo "Stopped PID(s): $pids"
  else
    echo "No listener on port $PORT."
  fi
else
  echo "Install fuser (psmisc) or lsof for stop_web.sh, or use Ctrl+C."
  exit 1
fi
