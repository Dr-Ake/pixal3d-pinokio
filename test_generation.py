import sys
import os
import torch
from pathlib import Path

# Set Blackwell environment variables so it matches start_wsl.sh
os.environ["ATTN_BACKEND"] = "sdpa"
os.environ["SPARSE_ATTN_BACKEND"] = "sdpa"
os.environ["SPARSE_CONV_BACKEND"] = "flex_gemm"

if os.environ.get("HF_TOKEN") and not os.environ.get("HUGGING_FACE_HUB_TOKEN"):
    os.environ["HUGGING_FACE_HUB_TOKEN"] = os.environ["HF_TOKEN"]
elif os.environ.get("HUGGING_FACE_HUB_TOKEN") and not os.environ.get("HF_TOKEN"):
    os.environ["HF_TOKEN"] = os.environ["HUGGING_FACE_HUB_TOKEN"]
elif os.environ.get("PIXAL3D_REMBG_MODEL") and not os.environ.get("HF_TOKEN"):
    print("HF_TOKEN is not set; gated custom Hugging Face model downloads may fail.")

launcher_root = Path(__file__).resolve().parent
wsl_root = Path(os.environ.get("PIXAL3D_WSL_ROOT", Path.home() / ".pinokio-pixal3d")).expanduser()
app_root = wsl_root / "app"

if not app_root.exists():
    raise SystemExit(f"Pixal3D WSL app folder not found: {app_root}")

# Change directory to the app path so it finds 'assets' and other app-local paths
os.chdir(app_root)

# Add workspace and app path to sys.path
sys.path.insert(0, str(app_root))
sys.path.insert(0, str(launcher_root))

# Patch natten backends
import launch
launch.force_natten_flex_on_blackwell()
launch.prefer_public_rembg_model()

import app as pixal3d_app

# Run pre-initialization
pixal3d_app.LOW_VRAM = False
pixal3d_app.init_models()

# Mock image dict
image_dict = {"path": str(launcher_root / "bus.png")}

print("Calling generate_3d directly...")
res = pixal3d_app.generate_3d(
    image=image_dict,
    seed=42,
    resolution=1536,
    session_id="test_session"
)
print("Finished generate_3d successfully!")
print("Result state path:", res["state_path"])
