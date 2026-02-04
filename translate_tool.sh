#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_NAME="translate-tool"
PID_DIR="$ROOT_DIR/.run"
LOG_DIR="$PID_DIR/logs"

BACKEND_HOST="${TRANSLATE_TOOL_HOST:-127.0.0.1}"
BACKEND_PORT="${TRANSLATE_TOOL_PORT:-8765}"
FRONTEND_PORT="5173"
OLLAMA_URL="${OLLAMA_BASE_URL:-http://localhost:11434}"

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

# Check if port is in use and kill the process if needed
ensure_port_free() {
  local port="$1"
  local service_name="$2"

  # Find PIDs using the port
  local pids
  pids=$(lsof -t -i :"$port" 2>/dev/null || true)

  if [[ -n "$pids" ]]; then
    echo "Port $port is occupied. Checking processes..."

    for pid in $pids; do
      # Get process info
      local proc_info
      proc_info=$(ps -p "$pid" -o pid=,cmd= 2>/dev/null || true)

      if [[ -n "$proc_info" ]]; then
        # Check if it's our own service (from Translate_Tool)
        if echo "$proc_info" | grep -q "Translate_Tool"; then
          echo "  Found existing Translate_Tool process (PID $pid), stopping it..."
        else
          echo "  Found foreign process occupying port $port:"
          echo "    PID $pid: $proc_info"
          echo "  Terminating process..."
        fi

        # Kill the process and its children
        kill -- -"$pid" 2>/dev/null || kill "$pid" 2>/dev/null || true

        # Wait for process to exit
        local timeout=5
        while kill -0 "$pid" 2>/dev/null && [[ $timeout -gt 0 ]]; do
          sleep 1
          timeout=$((timeout - 1))
        done

        # Force kill if still running
        if kill -0 "$pid" 2>/dev/null; then
          echo "  Force killing PID $pid..."
          kill -9 -- -"$pid" 2>/dev/null || kill -9 "$pid" 2>/dev/null || true
        fi
      fi
    done

    # Verify port is now free
    sleep 1
    if lsof -i :"$port" >/dev/null 2>&1; then
      echo "Warning: Port $port may still be in use. Service may fail to start." >&2
    else
      echo "Port $port is now free."
    fi
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

# Unload Ollama models to release GPU/VRAM
unload_ollama_models() {
  echo "Checking for loaded Ollama models..."

  # Check if Ollama is running
  if ! curl -s "$OLLAMA_URL/api/tags" >/dev/null 2>&1; then
    echo "  Ollama is not running, skipping model unload."
    return 0
  fi

  # Get list of currently loaded models via /api/ps
  local loaded_models
  loaded_models=$(curl -s "$OLLAMA_URL/api/ps" 2>/dev/null | grep -oP '"name"\s*:\s*"\K[^"]+' || true)

  if [[ -z "$loaded_models" ]]; then
    echo "  No models currently loaded in VRAM."
    return 0
  fi

  echo "  Found loaded models: $loaded_models"

  # Unload each model by setting keep_alive to 0
  for model in $loaded_models; do
    echo "  Unloading model: $model"
    local response
    response=$(curl -s -X POST "$OLLAMA_URL/api/generate" \
      -H "Content-Type: application/json" \
      -d "{\"model\": \"$model\", \"prompt\": \"\", \"keep_alive\": 0}" 2>&1)

    if echo "$response" | grep -q '"done"'; then
      echo "    Model $model unloaded successfully (VRAM released)"
    else
      echo "    Warning: Could not confirm unload for $model"
    fi
  done

  echo "  Ollama models unloaded."
}

# Release occupied resources
release_resources() {
  echo "Releasing resources..."

  # 0. Unload Ollama models to release GPU/VRAM
  unload_ollama_models

  # 1. Clean up stale PID files
  if [[ -d "$PID_DIR" ]]; then
    for pid_file in "$PID_DIR"/*.pid; do
      [[ -f "$pid_file" ]] || continue
      local pid
      pid="$(cat "$pid_file" 2>/dev/null || true)"
      if [[ -n "$pid" ]] && ! kill -0 "$pid" 2>/dev/null; then
        echo "  Removing stale PID file: $(basename "$pid_file")"
        rm -f "$pid_file"
      fi
    done
  fi

  # 2. Kill orphan processes related to this project
  local orphans
  orphans=$(pgrep -f "Translate_Tool.*(python|node|npm|vite)" 2>/dev/null || true)
  if [[ -n "$orphans" ]]; then
    echo "  Found orphan processes, terminating..."
    for pid in $orphans; do
      local proc_info
      proc_info=$(ps -p "$pid" -o pid=,cmd= 2>/dev/null || true)
      if [[ -n "$proc_info" ]]; then
        echo "    Killing PID $pid"
        kill "$pid" 2>/dev/null || true
      fi
    done
    sleep 1
    # Force kill if still running
    for pid in $orphans; do
      if kill -0 "$pid" 2>/dev/null; then
        kill -9 "$pid" 2>/dev/null || true
      fi
    done
  fi

  # 3. Ensure ports are free
  ensure_port_free "$BACKEND_PORT" "backend"
  ensure_port_free "$FRONTEND_PORT" "frontend"

  # 4. Clean up temporary files (older than 1 day)
  local temp_dirs=(
    "$ROOT_DIR/temp"
    "$ROOT_DIR/.tmp"
    "/tmp/translate_tool_*"
  )
  for temp_dir in "${temp_dirs[@]}"; do
    if [[ -d "$temp_dir" ]]; then
      local old_files
      old_files=$(find "$temp_dir" -type f -mtime +1 2>/dev/null | wc -l)
      if [[ "$old_files" -gt 0 ]]; then
        echo "  Cleaning $old_files old temp files in $temp_dir"
        find "$temp_dir" -type f -mtime +1 -delete 2>/dev/null || true
      fi
    fi
  done

  # 5. Clean up old log files (keep last 5)
  if [[ -d "$LOG_DIR" ]]; then
    for log_pattern in backend frontend; do
      local log_count
      log_count=$(ls -1 "$LOG_DIR/${log_pattern}"*.log 2>/dev/null | wc -l)
      if [[ "$log_count" -gt 5 ]]; then
        echo "  Rotating old $log_pattern logs"
        ls -1t "$LOG_DIR/${log_pattern}"*.log 2>/dev/null | tail -n +6 | xargs -r rm -f
      fi
    done
  fi

  echo "Resources released."
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

    # Release any occupied resources before starting
    release_resources

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
    release_resources
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
