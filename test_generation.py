import sys
import os
import torch

# Set Blackwell environment variables so it matches start_wsl.sh
os.environ["ATTN_BACKEND"] = "sdpa"
os.environ["SPARSE_ATTN_BACKEND"] = "sdpa"
os.environ["SPARSE_CONV_BACKEND"] = "flex_gemm"

# Load HF_TOKEN from ENVIRONMENT file
env_path = "/mnt/c/pinokio/api/pixal3d/ENVIRONMENT"
if os.path.exists(env_path):
    with open(env_path, "r") as f:
        for line in f:
            if line.strip().startswith("HF_TOKEN="):
                token = line.strip().split("=", 1)[1]
                os.environ["HF_TOKEN"] = token
                os.environ["HUGGING_FACE_HUB_TOKEN"] = token
                print("Loaded HF_TOKEN from ENVIRONMENT file")

# Change directory to the app path so it finds 'assets' and other app-local paths
os.chdir("/home/drake/.pinokio-pixal3d/app")

# Add workspace and app path to sys.path
sys.path.insert(0, "/home/drake/.pinokio-pixal3d/app")
sys.path.insert(0, "/mnt/c/pinokio/api/pixal3d")

# Patch natten backends
import launch
launch.force_natten_flex_on_blackwell()

import app as pixal3d_app

# Run pre-initialization
pixal3d_app.LOW_VRAM = False
pixal3d_app.init_models()

# Mock image dict
image_dict = {"path": "/mnt/c/pinokio/api/pixal3d/bus.png"}

print("Calling generate_3d directly...")
res = pixal3d_app.generate_3d(
    image=image_dict,
    seed=42,
    resolution=1536,
    session_id="test_session"
)
print("Finished generate_3d successfully!")
print("Result state path:", res["state_path"])
