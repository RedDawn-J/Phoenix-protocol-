#!/usr/bin/env bash
set -eo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PID_FILE="$ROOT/data/run/phoenix.pids"
if [ ! -f "$PID_FILE" ]; then echo "Phoenix is not running."; exit 0; fi
while IFS= read -r pid; do
  case "$pid" in ""|*[!0-9]*) continue ;; esac
  if kill -0 "$pid" 2>/dev/null; then
    command_line="$(ps -p "$pid" -o args= 2>/dev/null || true)"
    case "$command_line" in *"uvicorn server:app"*|*"serve-build.js"*) kill "$pid" 2>/dev/null || true ;; *) echo "Skipping unrelated PID $pid" ;; esac
  fi
done < "$PID_FILE"
rm -f "$PID_FILE"
echo "Phoenix stopped."
