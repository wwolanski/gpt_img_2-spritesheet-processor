#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
SERVICE_PORT="${RIFE_PORT:-8775}"
SERVICE_NAME="spritesheet-processor-frame-interpolation.service"
PID_FILE="frame_interpolation_service.pid"
LOG_FILE="frame_interpolation_service.log"

pid_is_running() {
  [[ "${1:-}" =~ ^[0-9]+$ ]] && kill -0 "$1" 2>/dev/null
}

if systemctl --user cat "$SERVICE_NAME" >/dev/null 2>&1; then
  systemctl --user start "$SERVICE_NAME"
  for _ in $(seq 1 60); do
    if curl -fsS --max-time 1 "http://127.0.0.1:$SERVICE_PORT/health" >/dev/null 2>&1; then
      printf 'Frame interpolation user-service running on http://127.0.0.1:%s.\n' "$SERVICE_PORT"
      exit 0
    fi
    sleep 1
  done
  printf 'Frame interpolation user-service failed to become ready.\n' >&2
  exit 1
fi

if [ -f "$PID_FILE" ] && pid_is_running "$(cat "$PID_FILE")"; then
  printf 'Frame interpolation service already running (PID %s).\n' "$(cat "$PID_FILE")"
  exit 0
fi
if [ ! -x .venv/bin/python ]; then
  printf 'Missing RIFE environment. Run ./setup_venv.sh before starting.\n' >&2
  exit 1
fi

nohup setsid env RIFE_PORT="$SERVICE_PORT" ./start.sh >"$LOG_FILE" 2>&1 < /dev/null &
pid="$!"
printf '%s\n' "$pid" > "$PID_FILE"

for _ in $(seq 1 60); do
  if curl -fsS --max-time 1 "http://127.0.0.1:$SERVICE_PORT/health" >/dev/null 2>&1; then
    printf 'Frame interpolation service running on http://127.0.0.1:%s pid=%s\n' "$SERVICE_PORT" "$pid"
    exit 0
  fi
  if ! kill -0 "$pid" 2>/dev/null; then
    break
  fi
  sleep 1
done

printf 'Frame interpolation service failed to start; see %s.\n' "$LOG_FILE" >&2
kill -- "-$pid" 2>/dev/null || kill "$pid" 2>/dev/null || true
rm -f "$PID_FILE"
exit 1
