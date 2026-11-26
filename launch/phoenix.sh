#!/usr/bin/env bash
set -eo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="$(command -v python3 || true)"
NODE="$(command -v node || true)"
if [ -n "$PHOENIX_PYTHON" ]; then PYTHON="$PHOENIX_PYTHON"; fi
if [ -n "$PHOENIX_NODE" ]; then NODE="$PHOENIX_NODE"; fi
[ -x "$PYTHON" ] || { echo "Python 3 is required (or set PHOENIX_PYTHON)." >&2; exit 2; }
[ -x "$NODE" ] || { echo "Node.js is required (or set PHOENIX_NODE)." >&2; exit 2; }
[ -f "$ROOT/frontend/build/index.html" ] || { echo "Build frontend first: frontend/build/index.html is missing." >&2; exit 3; }
"$PYTHON" -m uvicorn --version >/dev/null 2>&1 || { echo "Install backend/requirements.txt first." >&2; exit 4; }
BACKEND_PORT=8001
FRONTEND_PORT=3000
if [ -n "$PHOENIX_BACKEND_PORT" ]; then BACKEND_PORT="$PHOENIX_BACKEND_PORT"; fi
if [ -n "$PHOENIX_FRONTEND_PORT" ]; then FRONTEND_PORT="$PHOENIX_FRONTEND_PORT"; fi
DATA_DIR="$ROOT/data"
LOG_DIR="$ROOT/logs"
RUN_DIR="$DATA_DIR/run"
PID_FILE="$RUN_DIR/phoenix.pids"
WORKSPACE_ROOT="$ROOT/workspace"
mkdir -p "$DATA_DIR" "$LOG_DIR" "$RUN_DIR" "$WORKSPACE_ROOT"
if [ -f "$PID_FILE" ]; then echo "Phoenix appears to be running; run launch/phoenix-stop.sh first." >&2; exit 5; fi
export J_CLOUD_PROFILE=portable
export J_CLOUD_ROOT="$ROOT"
export J_CLOUD_DB="$DATA_DIR/phoenix.sqlite3"
export WORKSPACE_ROOT
export LOCAL_AUTH=1
if [ -z "$LOCAL_LLM_BASE_URL" ]; then export LOCAL_LLM_BASE_URL=http://127.0.0.1:11434/v1; fi
if [ -z "$LOCAL_LLM_MODEL" ]; then export LOCAL_LLM_MODEL=llama3.2; fi
export CORS_ORIGINS="http://127.0.0.1:$FRONTEND_PORT,http://localhost:$FRONTEND_PORT"
export PHOENIX_BACKEND_URL="http://127.0.0.1:$BACKEND_PORT"
export PYTHONPATH="$ROOT/backend:$PYTHONPATH"
umask 077
nohup "$PYTHON" -m uvicorn server:app --app-dir "$ROOT/backend" --host 127.0.0.1 --port "$BACKEND_PORT" >"$LOG_DIR/backend.log" 2>&1 &
BACKEND_PID=$!
nohup "$NODE" "$ROOT/launch/serve-build.js" "$ROOT/frontend/build" "$FRONTEND_PORT" >"$LOG_DIR/frontend.log" 2>&1 &
FRONTEND_PID=$!
printf "%s\n%s\n" "$BACKEND_PID" "$FRONTEND_PID" > "$PID_FILE"
READY=0
for i in $(seq 1 40); do
  if curl -fsS "http://127.0.0.1:$BACKEND_PORT/api/" >/dev/null 2>&1 && curl -fsS "http://127.0.0.1:$FRONTEND_PORT/" >/dev/null 2>&1; then READY=1; break; fi
  sleep 0.5
done
if [ "$READY" -ne 1 ]; then echo "Phoenix failed to start; inspect $LOG_DIR." >&2; "$ROOT/launch/phoenix-stop.sh" || true; exit 6; fi
echo "Phoenix ready at http://127.0.0.1:$FRONTEND_PORT"
case "$(uname -s)" in Darwin) open "http://127.0.0.1:$FRONTEND_PORT" >/dev/null 2>&1 || true ;; Linux) xdg-open "http://127.0.0.1:$FRONTEND_PORT" >/dev/null 2>&1 || true ;; esac
