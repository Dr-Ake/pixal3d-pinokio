#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LAUNCHER_ROOT="${PIXAL3D_LAUNCHER_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"
PATCH_DIR="${PIXAL3D_PATCH_DIR:-$LAUNCHER_ROOT/patches/upstream}"
MODE="apply"
APP_DIR=""
BACKUP_DIR=""

usage() {
  cat <<'EOF'
Usage: scripts/apply_patches.sh [--apply|--check|--unapply] [app-dir]

Applies the Pixal3D launcher patch overlay to an upstream TencentARC/Pixal3D
checkout. The default app-dir is ./app unless .wsl_root exists.
EOF
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --apply)
      MODE="apply"
      ;;
    --check)
      MODE="check"
      ;;
    --unapply)
      MODE="unapply"
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      if [ -n "$APP_DIR" ]; then
        usage >&2
        exit 2
      fi
      APP_DIR="$1"
      ;;
  esac
  shift
done

if [ -z "$APP_DIR" ]; then
  if [ -s "$LAUNCHER_ROOT/.wsl_root" ]; then
    WSL_ROOT="$(tr -d '\r\n' < "$LAUNCHER_ROOT/.wsl_root")"
    APP_DIR="$WSL_ROOT/app"
  else
    APP_DIR="$LAUNCHER_ROOT/app"
  fi
fi

case "$APP_DIR" in
  /*) ;;
  *) APP_DIR="$LAUNCHER_ROOT/$APP_DIR" ;;
esac

PATCHES=(
  "$PATCH_DIR/0001-pinokio-app-export-api.patch"
  "$PATCH_DIR/0002-pinokio-index-export-ui.patch"
  "$PATCH_DIR/0003-pinokio-pipeline-memory-cleanup.patch"
  "$PATCH_DIR/0004-pinokio-dinov3-layer-compat.patch"
)

PATCHED_PATHS=(
  "app.py"
  "index.html"
  "pixal3d/pipelines/pixal3d_image_to_3d.py"
  "pixal3d/trainers/flow_matching/mixins/image_conditioned_proj.py"
  "pixal3d/trainers/flow_matching/mixins/image_conditioned.py"
  "pixal3d/modules/image_feature_extractor.py"
)

git_app() {
  git -C "$APP_DIR" "$@"
}

create_backup() {
  local stamp candidate n
  stamp="$(date -u +%Y%m%dT%H%M%SZ)"
  candidate="$LAUNCHER_ROOT/cache/patch-backups/$stamp"
  n=1
  while [ -e "$candidate" ]; do
    candidate="$LAUNCHER_ROOT/cache/patch-backups/${stamp}-$n"
    n=$((n + 1))
  done

  BACKUP_DIR="$candidate"
  mkdir -p "$BACKUP_DIR"
  git_app rev-parse HEAD > "$BACKUP_DIR/upstream-head.txt" 2>/dev/null || true
  git_app status --short > "$BACKUP_DIR/status-before.txt" 2>/dev/null || true
  git_app diff --binary > "$BACKUP_DIR/worktree.diff" 2>/dev/null || true
  for patch in "${PATCHES[@]}"; do
    basename "$patch"
  done > "$BACKUP_DIR/patches.txt"
}

is_known_path() {
  local path_to_check="$1"
  local known
  for known in "${PATCHED_PATHS[@]}"; do
    if [ "$path_to_check" = "$known" ]; then
      return 0
    fi
  done
  return 1
}

check_no_unexpected_dirty_files() {
  local status line changed_path unexpected=()
  status="$(git_app status --porcelain --untracked-files=no)"
  while IFS= read -r line; do
    [ -z "$line" ] && continue
    changed_path="${line:3}"
    if ! is_known_path "$changed_path"; then
      unexpected+=("$line")
    fi
  done <<< "$status"

  if [ "${#unexpected[@]}" -gt 0 ]; then
    echo "[Pixal3D] Refusing to patch because the upstream checkout has tracked changes outside the launcher patch set:" >&2
    printf '  %s\n' "${unexpected[@]}" >&2
    echo "[Pixal3D] Backup saved at: $BACKUP_DIR" >&2
    exit 1
  fi
}

patch_can_apply() {
  git_app apply --check --whitespace=nowarn "$1" >/dev/null 2>&1
}

patch_is_applied() {
  git_app apply --reverse --check --whitespace=nowarn "$1" >/dev/null 2>&1
}

check_each_patch() {
  local patch ok=0
  for patch in "${PATCHES[@]}"; do
    if patch_is_applied "$patch"; then
      echo "[Pixal3D] $(basename "$patch") is already applied."
    elif patch_can_apply "$patch"; then
      echo "[Pixal3D] $(basename "$patch") can be applied."
    else
      ok=1
    fi
  done
  return "$ok"
}

apply_missing() {
  local patch
  for patch in "${PATCHES[@]}"; do
    if patch_is_applied "$patch"; then
      echo "[Pixal3D] $(basename "$patch") is already applied; skipping."
    elif patch_can_apply "$patch"; then
      echo "[Pixal3D] Applying $(basename "$patch")"
      git_app apply --whitespace=nowarn "$patch"
    else
      diagnose_failure "apply patches"
      fail_conflict
    fi
  done
}

reverse_applied() {
  local i patch
  for ((i=${#PATCHES[@]} - 1; i >= 0; i--)); do
    patch="${PATCHES[$i]}"
    if patch_can_apply "$patch"; then
      echo "[Pixal3D] $(basename "$patch") is not applied; skipping."
    elif patch_is_applied "$patch"; then
      echo "[Pixal3D] Removing $(basename "$patch")"
      git_app apply --reverse --whitespace=nowarn "$patch"
    else
      diagnose_failure "unapply patches"
      fail_conflict
    fi
  done
}

diagnose_failure() {
  local direction="$1"
  local patch
  echo "[Pixal3D] Patch check failed while trying to $direction." >&2
  for patch in "${PATCHES[@]}"; do
    echo "[Pixal3D] Checking $(basename "$patch")..." >&2
    if [ "$direction" = "unapply patches" ]; then
      git_app apply --reverse --check --whitespace=nowarn "$patch" >&2 || true
    else
      git_app apply --check --whitespace=nowarn "$patch" >&2 || true
    fi
  done
}

fail_conflict() {
  echo "[Pixal3D] Patch conflict detected." >&2
  echo "[Pixal3D] Backup saved at: $BACKUP_DIR" >&2
  echo "[Pixal3D] Upstream changed an area touched by this launcher's patches, or the app checkout was edited manually." >&2
  echo "[Pixal3D] Stopping instead of overwriting behavior. Refresh the patches before updating further." >&2
  exit 1
}

if [ ! -d "$APP_DIR/.git" ]; then
  echo "[Pixal3D] ERROR: app checkout not found at $APP_DIR" >&2
  exit 1
fi

for patch in "${PATCHES[@]}"; do
  if [ ! -s "$patch" ]; then
    echo "[Pixal3D] ERROR: missing patch file $patch" >&2
    exit 1
  fi
done

create_backup
check_no_unexpected_dirty_files

echo "[Pixal3D] Patch mode: $MODE"
echo "[Pixal3D] App checkout: $APP_DIR"
echo "[Pixal3D] Backup saved at: $BACKUP_DIR"

case "$MODE" in
  check)
    if check_each_patch; then
      echo "[Pixal3D] Dry-run patch check passed."
    else
      diagnose_failure "apply patches"
      fail_conflict
    fi
    ;;
  unapply)
    if check_each_patch; then
      echo "[Pixal3D] Dry-run reverse patch check passed."
      reverse_applied
      echo "[Pixal3D] Applied patches removed before upstream update."
    else
      diagnose_failure "unapply patches"
      fail_conflict
    fi
    ;;
  apply)
    if check_each_patch; then
      echo "[Pixal3D] Dry-run patch check passed."
      apply_missing
      echo "[Pixal3D] Patches applied."
    else
      diagnose_failure "apply patches"
      fail_conflict
    fi
    ;;
  *)
    usage >&2
    exit 2
    ;;
esac
