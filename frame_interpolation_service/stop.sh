#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
SERVICE_NAME="spritesheet-processor-frame-interpolation.service"
LEGACY_SERVICE_NAME="game-frame-interpolation.service"
if systemctl --user is-active --quiet "$SERVICE_NAME"; then
  systemctl --user stop "$SERVICE_NAME"
  printf 'Frame interpolation user-service stopped.\n'
  exit 0
fi
if systemctl --user is-active --quiet "$LEGACY_SERVICE_NAME"; then
  systemctl --user stop "$LEGACY_SERVICE_NAME"
  printf 'Legacy frame interpolation user-service stopped.\n'
  exit 0
fi
if [ ! -f frame_interpolation_service.pid ]; then
  printf 'Frame interpolation service not running.\n'
  exit 0
fi

pid="$(cat frame_interpolation_service.pid)"
if kill -0 "$pid" 2>/dev/null; then
  kill -- "-$pid" 2>/dev/null || kill "$pid" 2>/dev/null || true
  for _ in $(seq 1 30); do
    kill -0 "$pid" 2>/dev/null || break
    sleep 0.2
  done
fi
rm -f frame_interpolation_service.pid
printf 'Frame interpolation service stopped.\n'
