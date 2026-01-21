#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_NAME="translate-tool"
PID_DIR="$ROOT_DIR/.run"
LOG_DIR="$PID_DIR/logs"

BACKEND_HOST="${TRANSLATE_TOOL_HOST:-127.0.0.1}"
BACKEND_PORT="${TRANSLATE_TOOL_PORT:-8765}"
FRONTEND_PORT="5173"

usage() {
  cat <<'EOF'
Usage: ./translate_tool.sh <start|stop|status>

start  - launch backend and frontend services
stop   - stop running services
status - show current service status
EOF
}

ensure_conda() {
  if ! command -v conda >/dev/null 2>&1; then
    echo "conda not found in PATH." >&2
    exit 1
  fi

  local conda_base
  conda_base="$(conda info --base 2>/dev/null || true)"
  if [[ -z "$conda_base" || ! -d "$conda_base" ]]; then
    echo "Unable to locate conda base." >&2
    exit 1
  fi

  # Temporarily disable strict unbound variable check for conda activation
  # (conda activation scripts may reference unset variables like MKL_INTERFACE_LAYER)
  set +u
  # shellcheck disable=SC1090
  source "$conda_base/etc/profile.d/conda.sh"

  if ! conda env list | awk 'NF{print $1}' | grep -qx "$ENV_NAME"; then
    set -u
    echo "Conda env '$ENV_NAME' not found." >&2
    echo "Create it with: conda env update -n $ENV_NAME -f app/backend/environment.yml" >&2
    exit 1
  fi

  if [[ "${CONDA_DEFAULT_ENV:-}" != "$ENV_NAME" ]]; then
    conda activate "$ENV_NAME"
  fi
  set -u
}

ensure_node() {
  if ! command -v node >/dev/null 2>&1 || ! command -v npm >/dev/null 2>&1; then
    echo "node/npm not found. Install Node.js before running." >&2
    exit 1
  fi
}

ensure_deps() {
  if [[ ! -d "$ROOT_DIR/app/frontend/node_modules" ]]; then
    echo "Missing frontend dependencies. Run: (cd app/frontend && npm install)" >&2
    exit 1
  fi
}

start_process() {
  local name="$1"
  shift
  local pid_file="$PID_DIR/$name.pid"
  local log_file="$LOG_DIR/$name.log"

  mkdir -p "$LOG_DIR"

  if [[ -f "$pid_file" ]]; then
    local pid
    pid="$(cat "$pid_file")"
    if kill -0 "$pid" 2>/dev/null; then
      echo "$name already running (pid $pid)"
      return 0
    fi
    rm -f "$pid_file"
  fi

  if command -v setsid >/dev/null 2>&1; then
    setsid "$@" >"$log_file" 2>&1 &
  else
    nohup "$@" >"$log_file" 2>&1 &
  fi

  local pid=$!
  echo "$pid" >"$pid_file"
  echo "Started $name (pid $pid). Logs: $log_file"
}

stop_process() {
  local name="$1"
  local pid_file="$PID_DIR/$name.pid"

  if [[ ! -f "$pid_file" ]]; then
    echo "$name not running"
    return 0
  fi

  local pid
  pid="$(cat "$pid_file")"
  if ! kill -0 "$pid" 2>/dev/null; then
    rm -f "$pid_file"
    echo "$name not running"
    return 0
  fi

  kill -- -"$pid" 2>/dev/null || kill "$pid" 2>/dev/null || true

  local timeout=10
  while kill -0 "$pid" 2>/dev/null && [[ $timeout -gt 0 ]]; do
    sleep 1
    timeout=$((timeout - 1))
  done

  if kill -0 "$pid" 2>/dev/null; then
    kill -9 -- -"$pid" 2>/dev/null || kill -9 "$pid" 2>/dev/null || true
  fi

  rm -f "$pid_file"
  echo "Stopped $name"
}

status_process() {
  local name="$1"
  local pid_file="$PID_DIR/$name.pid"
  if [[ -f "$pid_file" ]]; then
    local pid
    pid="$(cat "$pid_file")"
    if kill -0 "$pid" 2>/dev/null; then
      echo "$name running (pid $pid)"
      return 0
    fi
  fi
  echo "$name stopped"
}

wait_for_backend() {
  local timeout="${1:-20}"
  local url="http://${BACKEND_HOST}:${BACKEND_PORT}/api/health"

  echo -n "Waiting for backend to be ready..."
  local count=0
  while [[ $count -lt $timeout ]]; do
    if curl -s "$url" >/dev/null 2>&1; then
      echo " ready!"
      return 0
    fi
    echo -n "."
    sleep 1
    count=$((count + 1))
  done
  echo " timeout!"
  echo "Warning: Backend may not be fully ready. Check logs: $LOG_DIR/backend.log" >&2
  return 1
}

show_urls() {
  echo ""
  echo "========================================"
  echo "  Translate Tool is running!"
  echo "----------------------------------------"
  echo "  Frontend:  http://localhost:${FRONTEND_PORT}"
  echo "  Backend:   http://${BACKEND_HOST}:${BACKEND_PORT}"
  echo "========================================"
  echo ""
}

command="${1:-}"
case "$command" in
  start)
    ensure_conda
    ensure_node
    ensure_deps

    # Start backend with conda python
    start_process "backend" python -m app.backend.main

    # Start frontend
    start_process "frontend" bash -c "cd \"$ROOT_DIR/app/frontend\" && npm run dev"

    # Wait for backend and show URLs
    wait_for_backend 20 || true
    show_urls
    ;;
  stop)
    stop_process "frontend"
    stop_process "backend"
    ;;
  status)
    status_process "backend"
    status_process "frontend"
    ;;
  *)
    usage
    exit 1
    ;;
esac
