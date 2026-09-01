#!/usr/bin/env bash
set -euo pipefail

MODULE_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
RUNTIME_DIR="$MODULE_ROOT/.runtime"
ASSET_PIPELINE_HOST="${ASSET_PIPELINE_HOST:-127.0.0.1}"
ASSET_PIPELINE_PORT="${ASSET_PIPELINE_PORT:-5174}"
SAM3_PORT="${SAM3_PORT:-8765}"
RIFE_PORT="${RIFE_PORT:-8775}"
SEMANTIC_CLIENT_QWEN_BASE_URL="${SEMANTIC_CLIENT_QWEN_BASE_URL:-http://127.0.0.1:1234/v1}"

printf 'Asset Pipeline: '
if curl -fsS --max-time 3 "http://$ASSET_PIPELINE_HOST:$ASSET_PIPELINE_PORT/" >/dev/null 2>&1; then
  printf 'ready at http://%s:%s\n' "$ASSET_PIPELINE_HOST" "$ASSET_PIPELINE_PORT"
else
  printf 'stopped\n'
fi

printf 'SAM3 service: '
if curl -fsS --max-time 3 "http://127.0.0.1:$SAM3_PORT/health" >/dev/null 2>&1; then
  printf 'ready at http://127.0.0.1:%s\n' "$SAM3_PORT"
else
  printf 'stopped/unavailable\n'
fi

printf 'Semantic client: in-process; Qwen/LM Studio: '
if curl -fsS --max-time 3 "${SEMANTIC_CLIENT_QWEN_BASE_URL%/}/models" >/dev/null 2>&1; then
  printf 'ready at %s\n' "$SEMANTIC_CLIENT_QWEN_BASE_URL"
else
  printf 'unavailable at %s\n' "$SEMANTIC_CLIENT_QWEN_BASE_URL"
fi

printf 'RIFE service: '
if curl -fsS --max-time 3 "http://127.0.0.1:$RIFE_PORT/health" >/dev/null 2>&1; then
  printf 'ready at http://127.0.0.1:%s\n' "$RIFE_PORT"
else
  printf 'stopped/unavailable (optional)\n'
fi

if [ -f "$RUNTIME_DIR/client.pid" ]; then
  printf 'Frontend PID file: %s\n' "$(cat "$RUNTIME_DIR/client.pid")"
fi
