#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
pid=""
if [ -f sam3_service.pid ]; then
  pid="$(cat sam3_service.pid)"
fi

if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
  kill -- "-$pid" 2>/dev/null || kill "$pid" 2>/dev/null || true
  for _ in $(seq 1 45); do
    kill -0 "$pid" 2>/dev/null || break
    sleep 0.2
  done
fi

rm -f sam3_service.pid
printf 'SAM3 service stopped.\n'
