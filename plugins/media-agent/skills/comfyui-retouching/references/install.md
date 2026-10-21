# Installing ComfyUI for these workflows

```bash
mkdir -p "$COMFY_HOME" && cd "$COMFY_HOME"
git clone --depth 1 https://github.com/comfyanonymous/ComfyUI
git clone --depth 1 https://github.com/1038lab/ComfyUI-RMBG ComfyUI/custom_nodes/ComfyUI-RMBG
uv venv -p 3.12 .venv && uv pip install -p .venv/bin/python torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu130
uv pip install -p .venv/bin/python -r ComfyUI/requirements.txt -r ComfyUI/custom_nodes/ComfyUI-RMBG/requirements.txt
```

Model files, with the names the workflows expect (about 19 GB):

| File | Folder under `ComfyUI/models/` | Source |
|---|---|---|
| `z_image_turbo_bf16.safetensors` | `diffusion_models` | `Comfy-Org/z_image_turbo`, `split_files/` |
| `qwen_3_4b_fp8_mixed.safetensors` | `text_encoders` | same |
| `ae.safetensors` | `vae` | same |
| `4xRealWebPhoto_v4_dat2.safetensors` | `upscale_models` | `Phips/4xRealWebPhoto_v4_dat2` |
| `RealESRGAN_x4plus.pth` | `upscale_models` | Real-ESRGAN releases |
| BiRefNet-general (4 files) | `RMBG/BiRefNet` | `1038lab/BiRefNet` |
| `big-lama.pt` | `RMBG/Lama` | `1038lab/Lama` |

The node downloads the last two on first use; pre-downloading only avoids a
slow first job. There is no pre-converted fp8 Z-Image in the official repo;
the smaller variants are int8 and nvfp4. The fp8 server flag is NVIDIA-only.
