#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
LAUNCHER_ROOT="$(pwd)"
WSL_ROOT="${PIXAL3D_WSL_ROOT:-$HOME/.pinokio-pixal3d}"
MAMBA_DIR="$WSL_ROOT/micromamba"
MAMBA_ROOT="$WSL_ROOT/mamba-root"
MAMBA="$MAMBA_DIR/bin/micromamba"
ENV_DIR="$WSL_ROOT/env"
APP_DIR="$WSL_ROOT/app"

mkdir -p "$WSL_ROOT" "$MAMBA_DIR" "$MAMBA_ROOT" "$WSL_ROOT/cache"

if [ ! -x "$MAMBA" ]; then
  echo "[Pixal3D] Installing micromamba..."
  curl -Ls https://micro.mamba.pm/api/micromamba/linux-64/latest | tar -xvj -C "$MAMBA_DIR" bin/micromamba
fi

if [ ! -x "$ENV_DIR/bin/python" ]; then
  echo "[Pixal3D] Creating Python 3.10 environment..."
  MAMBA_ROOT_PREFIX="$MAMBA_ROOT" "$MAMBA" create -y -p "$ENV_DIR" -c conda-forge python=3.10 pip
fi

if [ ! -d "$APP_DIR/.git" ]; then
  echo "[Pixal3D] Cloning TencentARC/Pixal3D..."
  rm -rf "$APP_DIR"
  git clone https://github.com/TencentARC/Pixal3D.git "$APP_DIR"
fi

PY="$ENV_DIR/bin/python"
cd "$APP_DIR"

is_blackwell_gpu() {
  if ! command -v nvidia-smi >/dev/null 2>&1; then
    return 1
  fi
  nvidia-smi --query-gpu=compute_cap --format=csv,noheader 2>/dev/null | awk -F. '
    $1 >= 12 { found = 1 }
    END { exit found ? 0 : 1 }
  '
}

install_blackwell_stack() {
  echo "[Pixal3D] Blackwell GPU detected. Installing CUDA 12.8 PyTorch and compatible Pixal3D wheels..."
  "$PY" -m pip install --upgrade --force-reinstall \
    torch==2.8.0 torchvision==0.23.0 \
    --index-url https://download.pytorch.org/whl/cu128

  "$PY" -m pip install --upgrade --force-reinstall --no-deps \
    "https://github.com/LDYang694/Storages/releases/download/20260430/natten-0.21.0%2Btorch2.8cu128-cp310-cp310-linux_x86_64.whl" \
    "https://github.com/LDYang694/Storages/releases/download/20260430/flash_attn_3-3.0.0-cp39-abi3-linux_x86_64.whl" \
    "https://github.com/LDYang694/Storages/releases/download/20260430/cumesh-0.0.1-cp310-cp310-linux_x86_64.whl" \
    "https://github.com/LDYang694/Storages/releases/download/20260430/flex_gemm-1.0.0-cp310-cp310-linux_x86_64.whl" \
    "https://github.com/LDYang694/Storages/releases/download/20260430/o_voxel-0.0.1-cp310-cp310-linux_x86_64.whl" \
    "https://github.com/LDYang694/Storages/releases/download/20260430/nvdiffrast-0.4.0-cp310-cp310-linux_x86_64.whl" \
    "https://github.com/LDYang694/Storages/releases/download/20260430/nvdiffrec_render-0.0.0-cp310-cp310-linux_x86_64.whl"

  "$PY" - <<'PY'
import sys
import torch

print("[Pixal3D] Torch:", torch.__version__, "CUDA:", torch.version.cuda)
if torch.cuda.is_available():
    cap = torch.cuda.get_device_capability(0)
    arch = f"sm_{cap[0]}{cap[1]}"
    arch_list = torch.cuda.get_arch_list()
    print("[Pixal3D] GPU:", torch.cuda.get_device_name(0), arch)
    print("[Pixal3D] Torch arch list:", arch_list)
    if cap[0] >= 12 and arch not in arch_list:
        print(f"[Pixal3D] ERROR: this Torch build does not include {arch}.", file=sys.stderr)
        sys.exit(1)
PY
}

echo "[Pixal3D] Installing Python dependencies. This can take a while..."
"$PY" -m pip install --upgrade pip setuptools wheel
"$PY" -m pip install -r requirements-hfdemo.txt
"$PY" -m pip install --upgrade gradio gradio_client spaces nest_asyncio pandas lpips tensorboard
"$PY" -m pip install --force-reinstall --no-deps https://github.com/LDYang694/Storages/releases/download/20260430/utils3d-0.0.2-py3-none-any.whl

if is_blackwell_gpu; then
  install_blackwell_stack
  date -Iseconds > "$LAUNCHER_ROOT/.wsl_blackwell"
fi

printf "%s\n" "$WSL_ROOT" > "$LAUNCHER_ROOT/.wsl_root"
date -Iseconds > "$LAUNCHER_ROOT/.wsl_installed"
echo "[Pixal3D] Installed in WSL at $WSL_ROOT"
