#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LAUNCHER_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
APP_DIR="${1:-app}"

case "$APP_DIR" in
  /*) ;;
  *) APP_DIR="$LAUNCHER_ROOT/$APP_DIR" ;;
esac

OLD_PATCH_DIR="$(mktemp -d)"
OLD_APPLY_SCRIPT="$OLD_PATCH_DIR/apply_patches.sh"
PATCH_REMOVED=0

cleanup() {
  rm -rf "$OLD_PATCH_DIR"
}
trap cleanup EXIT

cp "$LAUNCHER_ROOT"/patches/upstream/*.patch "$OLD_PATCH_DIR"/
cp "$LAUNCHER_ROOT/scripts/apply_patches.sh" "$OLD_APPLY_SCRIPT"

run_old_apply_script() {
  PIXAL3D_LAUNCHER_ROOT="$LAUNCHER_ROOT" PIXAL3D_PATCH_DIR="$OLD_PATCH_DIR" bash "$OLD_APPLY_SCRIPT" "$@"
}

restore_old_patch_overlay() {
  if [ "$PATCH_REMOVED" = "1" ] && [ -d "$APP_DIR/.git" ]; then
    echo "[Pixal3D] Update did not complete. Restoring the previous launcher patch overlay..."
    run_old_apply_script "$APP_DIR" || true
  fi
}

run_or_restore() {
  local code
  set +e
  "$@"
  code=$?
  set -e
  if [ "$code" -ne 0 ]; then
    restore_old_patch_overlay
    exit "$code"
  fi
}

if [ -d "$APP_DIR/.git" ]; then
  run_old_apply_script --unapply "$APP_DIR"
  PATCH_REMOVED=1
fi

if [ -d "$LAUNCHER_ROOT/.git" ]; then
  run_or_restore git -C "$LAUNCHER_ROOT" pull --ff-only
fi

if [ -d "$APP_DIR/.git" ]; then
  run_or_restore git -C "$APP_DIR" pull --ff-only
  PATCH_REMOVED=0
  bash "$LAUNCHER_ROOT/scripts/apply_patches.sh" "$APP_DIR"
else
  echo "[Pixal3D] App checkout not found at $APP_DIR; install will clone it."
fi
