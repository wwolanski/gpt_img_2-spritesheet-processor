#!/usr/bin/env bash
set -euo pipefail

MODULE_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
RUNTIME_DIR="$MODULE_ROOT/.runtime"

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

if [ -f "$RUNTIME_DIR/client.pid" ]; then
  pid="$(cat "$RUNTIME_DIR/client.pid")"
  if pid_is_running "$pid"; then
    stop_process_group "$pid"
    printf 'Asset Pipeline frontend stopped (PID %s).\n' "$pid"
  fi
  rm -f "$RUNTIME_DIR/client.pid"
fi

if [ -f "$RUNTIME_DIR/sam3.started" ]; then
  (cd "$MODULE_ROOT/sam3_service" && ./stop.sh)
  rm -f "$RUNTIME_DIR/sam3.started"
fi

if [ -f "$RUNTIME_DIR/rife.started" ]; then
  (cd "$MODULE_ROOT/frame_interpolation_service" && ./stop.sh)
  rm -f "$RUNTIME_DIR/rife.started"
fi

printf 'Spritesheet processor services stopped.\n'
