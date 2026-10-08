#!/usr/bin/env bash
# Dirigent's Linux development launcher. All Linux-specific launcher support
# intentionally lives in linux-v1 so the Windows launcher remains independent.

set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd -P)"
VENV_DIR="$PROJECT_ROOT/.venv"
PYTHON="$VENV_DIR/bin/python"
BACKEND_SCRIPT="$PROJECT_ROOT/run_backend.py"
FRONTEND_DIR="$PROJECT_ROOT/frontend"
RUNTIME_DIR="$SCRIPT_DIR/runtime"
BACKEND_LOG="$RUNTIME_DIR/backend.log"
BACKEND_PID_FILE="$RUNTIME_DIR/backend.pid"
LOCK_FILE="$RUNTIME_DIR/launcher.lock"
HEALTH_URL="http://127.0.0.1:8000/health"
HEALTH_TIMEOUT_SECONDS="${DIRIGENT_HEALTH_TIMEOUT_SECONDS:-30}"
HEALTH_POLL_SECONDS="${DIRIGENT_HEALTH_POLL_SECONDS:-0.5}"

backend_only=false
managed_backend_pid=""
managed_frontend_pid=""
backend_reused=false
cleanup_done=false

usage() {
  cat <<'EOF'
Usage: run_dirigent.sh [--backend-only]

Starts Dirigent from any working directory. --backend-only leaves the managed
backend running until Ctrl+C or SIGTERM for API troubleshooting.
EOF
}

step() { printf '[%s/4] %s\n' "$1" "$2"; }
info() { printf '%s\n' "$*"; }
success() { printf '%s\n' "$*"; }
error() { printf 'ERROR: %s\n' "$*" >&2; }

show_backend_log() {
  if [[ -f "$BACKEND_LOG" ]]; then
    error "Recent backend log output ($BACKEND_LOG):"
    tail -n 30 "$BACKEND_LOG" >&2 || true
  fi
}

backend_is_healthy() {
  local response
  response="$(curl --silent --show-error --fail --max-time 2 "$HEALTH_URL" 2>/dev/null)" || return 1
  [[ "$response" =~ \"status\"[[:space:]]*:[[:space:]]*\"ok\" ]]
}

process_is_running() {
  [[ -n "$1" ]] && kill -0 "$1" 2>/dev/null || return 1
  # kill -0 succeeds for an unreaped zombie, which must count as exited while
  # startup health polling is deciding whether to abort.
  local state
  state="$(ps -o stat= -p "$1" 2>/dev/null || true)"
  [[ "$state" != Z* ]]
}

remove_own_pid_file() {
  if [[ -n "$managed_backend_pid" && -f "$BACKEND_PID_FILE" ]] \
    && [[ "$(<"$BACKEND_PID_FILE")" == "$managed_backend_pid" ]]; then
    rm -f -- "$BACKEND_PID_FILE"
  fi
}

stop_managed_backend() {
  [[ -n "$managed_backend_pid" ]] || return 0

  if process_is_running "$managed_backend_pid"; then
    info "Stopping managed backend (PID: $managed_backend_pid)..."
    # The backend is its own session/process group (setsid), so descendants do
    # not survive if uvicorn later creates any workers.
    kill -TERM -- "-$managed_backend_pid" 2>/dev/null || kill -TERM "$managed_backend_pid" 2>/dev/null || true
    for _ in {1..50}; do
      process_is_running "$managed_backend_pid" || break
      sleep 0.1
    done
    if process_is_running "$managed_backend_pid"; then
      error "Managed backend did not stop gracefully; sending SIGKILL."
      kill -KILL -- "-$managed_backend_pid" 2>/dev/null || kill -KILL "$managed_backend_pid" 2>/dev/null || true
    fi
  fi
  remove_own_pid_file
  managed_backend_pid=""
}

stop_managed_frontend() {
  [[ -n "$managed_frontend_pid" ]] || return 0
  if process_is_running "$managed_frontend_pid"; then
    info "Stopping frontend (PID: $managed_frontend_pid)..."
    kill -TERM -- "-$managed_frontend_pid" 2>/dev/null || kill -TERM "$managed_frontend_pid" 2>/dev/null || true
    for _ in {1..50}; do
      process_is_running "$managed_frontend_pid" || break
      sleep 0.1
    done
    if process_is_running "$managed_frontend_pid"; then
      kill -KILL -- "-$managed_frontend_pid" 2>/dev/null || kill -KILL "$managed_frontend_pid" 2>/dev/null || true
    fi
  fi
  managed_frontend_pid=""
}

cleanup() {
  local status=$?
  if [[ "$cleanup_done" != true ]]; then
    cleanup_done=true
    stop_managed_frontend
    # A reused backend is deliberately never assigned a managed PID.
    stop_managed_backend
  fi
  exit "$status"
}

on_signal() {
  info "Launcher interrupted; cleaning up."
  exit 130
}

wait_for_backend_health() {
  local deadline=$((SECONDS + HEALTH_TIMEOUT_SECONDS))
  local attempt=0
  info "Polling $HEALTH_URL (timeout: ${HEALTH_TIMEOUT_SECONDS}s)"

  while (( SECONDS < deadline )); do
    attempt=$((attempt + 1))
    if backend_is_healthy; then
      success "Backend is healthy (attempt $attempt)"
      return 0
    fi
    if ! process_is_running "$managed_backend_pid"; then
      error "Backend exited before becoming healthy."
      return 1
    fi
    sleep "$HEALTH_POLL_SECONDS"
  done

  error "Backend did not become healthy within ${HEALTH_TIMEOUT_SECONDS} seconds."
  return 1
}

start_backend() {
  : > "$BACKEND_LOG"
  # setsid gives this launcher ownership of a private process group. $! remains
  # the Python PID because setsid execs its command in this non-interactive use.
  setsid env API_PORT=8000 "$PYTHON" "$BACKEND_SCRIPT" --no-reload 9>&- >>"$BACKEND_LOG" 2>&1 &
  managed_backend_pid=$!
  local pid_tmp="$BACKEND_PID_FILE.tmp.$$"
  printf '%s\n' "$managed_backend_pid" > "$pid_tmp"
  mv -f -- "$pid_tmp" "$BACKEND_PID_FILE"
  success "Backend process started (PID: $managed_backend_pid); logging to $BACKEND_LOG"
}

while (($#)); do
  case "$1" in
    --backend-only) backend_only=true ;;
    -h|--help) usage; exit 0 ;;
    *) error "Unknown option: $1"; usage >&2; exit 2 ;;
  esac
  shift
done

umask 077
mkdir -p -- "$RUNTIME_DIR"
chmod 700 "$RUNTIME_DIR"
exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  error "Another Linux launcher instance is already active."
  exit 1
fi
trap cleanup EXIT
trap on_signal INT TERM HUP

cd -- "$PROJECT_ROOT"

step 1 "Activating virtual environment"
if [[ ! -d "$VENV_DIR" ]]; then
  error "Virtual environment not found at '$VENV_DIR'."
  error "Create it with Python 3.12: cd '$PROJECT_ROOT' && uv python install 3.12 && uv venv --python 3.12 .venv"
  error "Then install dependencies with: uv pip install --python .venv/bin/python -r backend/requirements.txt"
  exit 1
fi
if [[ ! -x "$PYTHON" ]]; then
  error "Python executable not found at '$PYTHON'. Recreate the .venv virtual environment."
  exit 1
fi
success "Virtual environment found."

step 2 "Starting backend"
if backend_is_healthy; then
  backend_reused=true
  success "Backend is already running and healthy; reusing it."
else
  if [[ -f "$BACKEND_PID_FILE" ]]; then
    info "Replacing stale launcher PID record at $BACKEND_PID_FILE."
  fi
  start_backend
fi

step 3 "Waiting for backend health"
if [[ "$backend_reused" == true ]]; then
  success "Backend is already healthy."
elif ! wait_for_backend_health; then
  show_backend_log
  exit 1
fi

if [[ "$backend_only" == true ]]; then
  step 4 "Frontend skipped (backend-only mode)"
  success "Dirigent is ready. Backend is available at $HEALTH_URL"
  if [[ "$backend_reused" != true ]]; then
    info "Press Ctrl+C to stop the managed backend."
    # Waiting on the child preserves ownership until it exits or a signal runs cleanup.
    if wait "$managed_backend_pid"; then
      :
    else
      backend_status=$?
      error "Backend exited with code $backend_status."
      show_backend_log
      exit "$backend_status"
    fi
  fi
  exit 0
fi

step 4 "Launching frontend"
if ! command -v npm >/dev/null 2>&1; then
  error "npm was not found. Install Node.js/npm, then run: cd '$FRONTEND_DIR' && npm install"
  exit 1
fi
if [[ ! -d "$FRONTEND_DIR/node_modules" ]]; then
  error "Frontend dependencies are missing. Install them with: cd '$FRONTEND_DIR' && npm install"
  exit 1
fi

success "Dirigent is ready."
(
  cd -- "$FRONTEND_DIR"
  exec setsid npm run tauri dev 9>&-
) &
managed_frontend_pid=$!
if wait "$managed_frontend_pid"; then
  managed_frontend_pid=""
else
  frontend_status=$?
  managed_frontend_pid=""
  error "Frontend exited with code $frontend_status."
  exit "$frontend_status"
fi
