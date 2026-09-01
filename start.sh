#!/usr/bin/env bash
set -euo pipefail

MODULE_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
RUNTIME_DIR="$MODULE_ROOT/.runtime"
PYTHON_BIN="${ASSET_PIPELINE_PYTHON:-$MODULE_ROOT/.venv/bin/python}"
ASSET_PIPELINE_HOST="${ASSET_PIPELINE_HOST:-127.0.0.1}"
ASSET_PIPELINE_PORT="${ASSET_PIPELINE_PORT:-5174}"
SAM3_PORT="${SAM3_PORT:-8765}"
SEMANTIC_CLIENT_QWEN_BASE_URL="${SEMANTIC_CLIENT_QWEN_BASE_URL:-http://127.0.0.1:1234/v1}"
export SEMANTIC_CLIENT_QWEN_BASE_URL
START_SAM3="${START_SAM3:-0}"
START_RIFE="${START_RIFE:-0}"
started_sam3=0
started_rife=0

mkdir -p "$RUNTIME_DIR"

pid_is_running() {
  [[ "${1:-}" =~ ^[0-9]+$ ]] && kill -0 "$1" 2>/dev/null
}

stop_process_group() {
  local pid="$1"
  if ! pid_is_running "$pid"; then
    return 0
  fi
  kill -- "-$pid" 2>/dev/null || kill "$pid" 2>/dev/null || true
  for _ in $(seq 1 30); do
    pid_is_running "$pid" || return 0
    sleep 0.2
  done
  kill -KILL -- "-$pid" 2>/dev/null || kill -KILL "$pid" 2>/dev/null || true
}

cleanup_failed_start() {
  local status="$?"
  if [ "$status" -ne 0 ]; then
    if [ "$started_rife" = "1" ]; then
      (cd "$MODULE_ROOT/frame_interpolation_service" && ./stop.sh) || true
      rm -f "$RUNTIME_DIR/rife.started"
    fi
    if [ "$started_sam3" = "1" ]; then
      (cd "$MODULE_ROOT/sam3_service" && ./stop.sh) || true
      rm -f "$RUNTIME_DIR/sam3.started"
    fi
  fi
  trap - EXIT
  exit "$status"
}
trap cleanup_failed_start EXIT

if [ ! -x "$PYTHON_BIN" ]; then
  printf 'Missing Python environment: %s\nRun ./setup_venv.sh first, or set ASSET_PIPELINE_PYTHON.\n' "$PYTHON_BIN" >&2
  exit 1
fi

if ! "$PYTHON_BIN" -c 'import semantic_client' >/dev/null 2>&1; then
  printf 'Local semantic_client cannot be imported with %s.\n' "$PYTHON_BIN" >&2
  exit 1
fi

if [ "$START_SAM3" = "1" ] && [ ! -x "$MODULE_ROOT/sam3_service/.venv/bin/python" ]; then
  printf 'SAM3 environment is missing. Run sam3_service/setup_venv.sh before starting it.\n' >&2
  exit 1
fi

if [ ! -d "$MODULE_ROOT/client/node_modules" ]; then
  printf 'Frontend dependencies are missing. Run (cd client && npm ci) before starting.\n' >&2
  exit 1
fi

if [ "$START_SAM3" = "1" ]; then
  if curl -fsS --max-time 3 "http://127.0.0.1:$SAM3_PORT/health" >/dev/null 2>&1; then
    printf 'SAM3 service already running on http://127.0.0.1:%s.\n' "$SAM3_PORT"
  else
    printf 'Starting SAM3 service on http://127.0.0.1:%s...\n' "$SAM3_PORT"
    (cd "$MODULE_ROOT/sam3_service" && SAM3_PORT="$SAM3_PORT" ./start_background.sh)
    : > "$RUNTIME_DIR/sam3.started"
    started_sam3=1
  fi
else
  printf 'SAM3 startup skipped (START_SAM3=%s).\n' "$START_SAM3"
fi

if [ "$START_RIFE" = "1" ]; then
  if curl -fsS --max-time 3 "http://127.0.0.1:${RIFE_PORT:-8775}/health" >/dev/null 2>&1; then
    printf 'RIFE service already running.\n'
  else
    printf 'Starting optional RIFE service...\n'
    (cd "$MODULE_ROOT/frame_interpolation_service" && ./start_background.sh)
    : > "$RUNTIME_DIR/rife.started"
    started_rife=1
  fi
fi

if [ -f "$RUNTIME_DIR/client.pid" ] && pid_is_running "$(cat "$RUNTIME_DIR/client.pid")"; then
  printf 'Asset Pipeline frontend already running (PID %s).\n' "$(cat "$RUNTIME_DIR/client.pid")"
else
  rm -f "$RUNTIME_DIR/client.pid"
  printf 'Starting Asset Pipeline frontend on http://%s:%s...\n' "$ASSET_PIPELINE_HOST" "$ASSET_PIPELINE_PORT"
  nohup setsid env \
    ASSET_PIPELINE_PYTHON="$PYTHON_BIN" \
    npm --prefix "$MODULE_ROOT/client" run dev -- --host "$ASSET_PIPELINE_HOST" --port "$ASSET_PIPELINE_PORT" \
    >"$RUNTIME_DIR/client.log" 2>&1 < /dev/null &
  client_pid="$!"
  printf '%s\n' "$client_pid" > "$RUNTIME_DIR/client.pid"
  ready=0
  for _ in $(seq 1 30); do
    if curl -fsS --max-time 1 "http://$ASSET_PIPELINE_HOST:$ASSET_PIPELINE_PORT/" >/dev/null 2>&1; then
      ready=1
      break
    fi
    pid_is_running "$client_pid" || break
    sleep 0.5
  done
  if [ "$ready" != "1" ]; then
    printf 'Asset Pipeline frontend failed to start; see %s.\n' "$RUNTIME_DIR/client.log" >&2
    stop_process_group "$client_pid"
    rm -f "$RUNTIME_DIR/client.pid"
    exit 1
  fi
fi

printf '\nSemantic client: in-process (not a separate server).\n'
printf 'Qwen/LM Studio endpoint: %s\n' "$SEMANTIC_CLIENT_QWEN_BASE_URL"
if curl -fsS --max-time 3 "${SEMANTIC_CLIENT_QWEN_BASE_URL%/}/models" >/dev/null 2>&1; then
  printf 'Qwen/LM Studio: ready\n'
else
  printf 'Qwen/LM Studio: unavailable (semantic proposal will be skipped)\n'
fi

printf '\nUse ./status.sh for health checks and ./stop.sh to stop the services.\n'
