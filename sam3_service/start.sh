#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  printf 'Missing SAM3 environment. Run ./setup_venv.sh before starting.\n' >&2
  exit 1
fi

SERVICE_ROOT="$(pwd -P)"
export SAM3_MODEL_PATH="${SAM3_MODEL_PATH:-$SERVICE_ROOT/models/sam3.1_multiplex_fp16.safetensors}"
export SAM3_DEVICE="${SAM3_DEVICE:-cuda}"
export SAM3_HALF="${SAM3_HALF:-1}"
export SAM3_IMGSZ="${SAM3_IMGSZ:-644}"
export PYTORCH_CUDA_ALLOC_CONF="${PYTORCH_CUDA_ALLOC_CONF:-expandable_segments:True}"
export SAM3_HOST="${SAM3_HOST:-127.0.0.1}"
export SAM3_PORT="${SAM3_PORT:-8765}"

exec .venv/bin/python -m uvicorn app.main:app --host "$SAM3_HOST" --port "$SAM3_PORT"
