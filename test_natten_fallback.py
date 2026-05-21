import sys
import os
import torch

# Add current workspace to path
sys.path.insert(0, os.getcwd())

# Patch natten backends
import launch
launch.force_natten_flex_on_blackwell()

from natten import na2d

# Create dummy inputs matching NAF's shapes in standard mode
# Query: [1, 128, 128, 4, 64]
# Key: [1, 128, 128, 4, 64]
# Value: [1, 128, 128, 4, 256]
query = torch.randn(1, 128, 128, 4, 64, device="cuda", dtype=torch.float16)
key = torch.randn(1, 128, 128, 4, 64, device="cuda", dtype=torch.float16)
value = torch.randn(1, 128, 128, 4, 256, device="cuda", dtype=torch.float16)

kernel_size = 9
dilation = 1
stride = 1

print("Calling na2d with mixed head dimensions...")
try:
    out = na2d(query, key, value, kernel_size=kernel_size, dilation=dilation, stride=stride, backend="cutlass-fna")
    print("na2d call returned successfully!")
    print("Output shape:", out.shape)
except Exception as e:
    print("na2d call failed!")
    import traceback
    traceback.print_exc()
