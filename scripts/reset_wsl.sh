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

case "$WSL_ROOT" in
  "$HOME"/.pinokio-pixal3d|"$HOME"/.pinokio-pixal3d/*)
    rm -rf "$WSL_ROOT"
    ;;
  *)
    echo "Refusing to remove unexpected WSL path: $WSL_ROOT"
    exit 1
    ;;
esac

rm -f "$LAUNCHER_ROOT/.wsl_installed" "$LAUNCHER_ROOT/.wsl_root" "$LAUNCHER_ROOT/.wsl_blackwell"
echo "[Pixal3D] WSL install reset."
