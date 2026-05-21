#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
LAUNCHER_ROOT="$(pwd)"

read_wsl_root() {
  if [ -n "${PIXAL3D_WSL_ROOT:-}" ]; then
    printf "%s" "$PIXAL3D_WSL_ROOT"
    return
  fi
  if [ -s "$LAUNCHER_ROOT/.wsl_root" ]; then
    local saved
    saved="$(tr -d '\r\n' < "$LAUNCHER_ROOT/.wsl_root")"
    if [ -n "$saved" ]; then
      printf "%s" "$saved"
      return
    fi
  fi
  printf "%s/.pinokio-pixal3d" "$HOME"
}

WSL_ROOT="$(read_wsl_root)"
APP_DIR="$WSL_ROOT/app"

bash "$LAUNCHER_ROOT/scripts/update_app.sh" "$APP_DIR"
bash "$LAUNCHER_ROOT/scripts/install_wsl.sh"
