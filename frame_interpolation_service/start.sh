#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  printf 'Missing RIFE environment. Run ./setup_venv.sh before starting.\n' >&2
  exit 1
fi

SERVICE_ROOT="$(pwd -P)"
export RIFE_MODEL_PATH="${RIFE_MODEL_PATH:-$SERVICE_ROOT/models/Practical-RIFE/train_log}"
export RIFE_DEVICE="${RIFE_DEVICE:-cuda}"
export RIFE_HALF="${RIFE_HALF:-0}"
export RIFE_HOST="${RIFE_HOST:-127.0.0.1}"
export RIFE_PORT="${RIFE_PORT:-8775}"

exec .venv/bin/python -m uvicorn app.main:app --host "$RIFE_HOST" --port "$RIFE_PORT"
