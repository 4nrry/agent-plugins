# Installing ComfyUI for these workflows

`COMFY_HOME` can be any directory. The scripts expect the ComfyUI clone and its
virtual environment side by side in it: `$COMFY_HOME/ComfyUI/main.py` and
`$COMFY_HOME/.venv/bin/python`.

```bash
export COMFY_HOME=~/.local/opt/comfyui
mkdir -p "$COMFY_HOME" && cd "$COMFY_HOME"
git clone --depth 1 --branch v0.45.0 https://github.com/Comfy-Org/ComfyUI
git clone https://github.com/1038lab/ComfyUI-RMBG ComfyUI/custom_nodes/ComfyUI-RMBG
git -C ComfyUI/custom_nodes/ComfyUI-RMBG checkout a66a5e641a54988d80ed6aad18946081c85f309e   # 3.3.0; the node has no tags
uv venv -p 3.12 .venv && uv pip install -p .venv/bin/python torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu130
uv pip install -p .venv/bin/python -r ComfyUI/requirements.txt -r ComfyUI/custom_nodes/ComfyUI-RMBG/requirements.txt
```

- **Repository.** ComfyUI lives at `Comfy-Org/ComfyUI`; the old
  `comfyanonymous/ComfyUI` address redirects there.
- **Release.** The pins are the install the workflows were last run on:
  ComfyUI v0.45.0, ComfyUI-RMBG 3.3.0 and torch 2.14.1+cu130 (checked on
  2026-11-11). Carried over, not re-run here: on that install `background`,
  `remove` and `upscale` ran and `generate` and `inpaint` did not (the
  machine's tooling audit of the same day); those two last ran on an earlier
  release. To move to a newer one, check out its tag, run the requirements
  line again, and run each workflow once.
- **Python.** The ComfyUI README at v0.45.0 recommends Python 3.13 and says to
  try 3.12 when a custom node's dependencies give trouble on 3.13. The
  commands use 3.12 because that is the version the workflows ran on. On 3.13
  the same requirements resolve (`uv pip compile`), but nothing was run there.
- **Torch.** The README's command for NVIDIA cards takes torch from the
  `cu130` wheel index and says a cu130 or newer build is required on the
  RTX 20 series and later.
- **Moving it.** Move `ComfyUI/` and `.venv/` together and point `COMFY_HOME`
  at the new place. The scripts call only `.venv/bin/python`, a link to uv's
  interpreter, which still works after a move; the other entry points in
  `.venv/bin/` (`pip`, `activate`) keep the old absolute path, so recreate the
  environment before using those.

Model files, with the names the workflows expect (about 19 GB):

| File | Folder under `ComfyUI/models/` | Source |
|---|---|---|
| `z_image_turbo_bf16.safetensors` | `diffusion_models` | `Comfy-Org/z_image_turbo`, `split_files/` |
| `qwen_3_4b_fp8_mixed.safetensors` | `text_encoders` | same |
| `ae.safetensors` | `vae` | same |
| `4xRealWebPhoto_v4_dat2.safetensors` | `upscale_models` | `Phips/4xRealWebPhoto_v4_dat2` |
| `RealESRGAN_x4plus.pth` (optional: no bundled workflow loads it) | `upscale_models` | Real-ESRGAN releases |
| BiRefNet-general (4 files) | `RMBG/BiRefNet` | `1038lab/BiRefNet` |
| `big-lama.pt` | `RMBG/Lama` | `1038lab/Lama` |

The node downloads the last two on first use; pre-downloading only avoids a
slow first job. There is no pre-converted fp8 Z-Image in the official repo;
the smaller variants are int8 and nvfp4. The fp8 server flag is NVIDIA-only.
