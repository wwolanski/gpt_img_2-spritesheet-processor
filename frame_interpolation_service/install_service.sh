#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  ./setup_venv.sh
fi

unit_dir="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
service_name="spritesheet-processor-frame-interpolation.service"
mkdir -p "$unit_dir"
service_root="$(pwd -P)"
python_bin="$service_root/.venv/bin/python"
sed \
  -e "s|__SERVICE_ROOT__|$service_root|g" \
  -e "s|__PYTHON_BIN__|$python_bin|g" \
  spritesheet-processor-frame-interpolation.service > "$unit_dir/$service_name"
systemctl --user daemon-reload
systemctl --user enable --now "$service_name"
systemctl --user --no-pager status "$service_name"
