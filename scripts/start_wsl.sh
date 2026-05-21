#!/usr/bin/env bash
set -euo pipefail

PORT="${1:?Missing port}"
MODE="${2:-low}"

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
ENV_DIR="$WSL_ROOT/env"
APP_DIR="$WSL_ROOT/app"
PY="$ENV_DIR/bin/python"

if [ ! -x "$PY" ] || [ ! -d "$APP_DIR" ]; then
  echo "Pixal3D is not installed in WSL yet. Run Install in WSL first."
  exit 1
fi

BLACKWELL=0
if command -v nvidia-smi >/dev/null 2>&1; then
  if nvidia-smi --query-gpu=compute_cap --format=csv,noheader 2>/dev/null | awk -F. '$1 >= 12 { found = 1 } END { exit found ? 0 : 1 }'; then
    BLACKWELL=1
  fi
fi

if [ "$BLACKWELL" = "1" ]; then
  "$PY" - <<'PY'
import sys
import torch

if torch.cuda.is_available():
    cap = torch.cuda.get_device_capability(0)
    arch = f"sm_{cap[0]}{cap[1]}"
    if cap[0] >= 12 and arch not in torch.cuda.get_arch_list():
        print("[Pixal3D] This RTX 50/Blackwell GPU needs the CUDA 12.8 Torch repair.")
        print("[Pixal3D] Click Update or Install again so the launcher can install the torch2.8/cu128 wheel set.")
        print("[Pixal3D] Current Torch:", torch.__version__, "CUDA:", torch.version.cuda, "arches:", torch.cuda.get_arch_list())
        sys.exit(42)
PY
fi

if [ "$BLACKWELL" = "1" ] && [ "$MODE" != "low" ]; then
  echo "[Pixal3D] Blackwell/RTX 50 detected. Standard mode is unstable in WSL with the current CUDA stack, so Low VRAM mode will be used."
  MODE="low"
fi

mkdir -p "$WSL_ROOT/cache/HF_HOME" "$WSL_ROOT/cache/TORCH_HOME" "$WSL_ROOT/cache/GRADIO_TEMP_DIR"

if [ "$BLACKWELL" = "1" ]; then
  export ATTN_BACKEND="${ATTN_BACKEND:-sdpa}"
  export SPARSE_ATTN_BACKEND="${SPARSE_ATTN_BACKEND:-sdpa}"
else
  export ATTN_BACKEND="${ATTN_BACKEND:-flash_attn_3}"
  export SPARSE_ATTN_BACKEND="${SPARSE_ATTN_BACKEND:-$ATTN_BACKEND}"
fi
export SPARSE_ATTN_BACKEND="${SPARSE_ATTN_BACKEND:-$ATTN_BACKEND}"
export SPARSE_CONV_BACKEND="${SPARSE_CONV_BACKEND:-flex_gemm}"
export PYTORCH_CUDA_ALLOC_CONF="${PYTORCH_CUDA_ALLOC_CONF:-expandable_segments:True}"
export OPENCV_IO_ENABLE_OPENEXR=1
export GRADIO_ANALYTICS_ENABLED=False
export HF_HOME="$WSL_ROOT/cache/HF_HOME"
export TORCH_HOME="$WSL_ROOT/cache/TORCH_HOME"
export GRADIO_TEMP_DIR="$WSL_ROOT/cache/GRADIO_TEMP_DIR"

if [ -n "${HF_TOKEN:-}" ] && [ -z "${HUGGING_FACE_HUB_TOKEN:-}" ]; then
  export HUGGING_FACE_HUB_TOKEN="$HF_TOKEN"
elif [ -z "${HF_TOKEN:-}" ] && [ -n "${HUGGING_FACE_HUB_TOKEN:-}" ]; then
  export HF_TOKEN="$HUGGING_FACE_HUB_TOKEN"
fi

if [ -z "${HF_TOKEN:-}" ]; then
  echo "[Pixal3D] HF_TOKEN is not set. briaai/RMBG-2.0 is gated, so first generation may fail until Hugging Face access is accepted and a read token is provided."
fi

LOW_VRAM_ARG=""
if [ "$MODE" = "low" ]; then
  export LOW_VRAM=1
  LOW_VRAM_ARG="--low_vram"
else
  export LOW_VRAM=0
fi

cd "$APP_DIR"
echo "Launching Pixal3D on port $PORT"
exec "$PY" "$LAUNCHER_ROOT/launch.py" --host 127.0.0.1 --port "$PORT" $LOW_VRAM_ARG
