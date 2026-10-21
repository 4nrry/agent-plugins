---
name: comfyui-retouching
description: Retouches and generates images with ComfyUI headless on an 8 GB GPU using only commercially licensed models — background removal (BiRefNet), photo upscaling (4xRealWebPhoto DAT2), removing a logo or object (LaMa), inpainting and stills (Z-Image Turbo). Use when a task involves ComfyUI, Stable Diffusion, FLUX, upscaling, removing a background, a transparent PNG, removing a watermark or logo from a frame, inpainting, local image generation, VRAM, or when someone plans to use 4x-UltraSharp, RMBG-2.0 or FLUX.1 dev in company work.
---

# ComfyUI retouching, headless

ComfyUI is an HTTP server; the UI is one client. The scripts start the server,
post an API-format graph, wait on `/history` and download the PNG.

## Use

From this skill's directory:

```bash
export COMFY_HOME=~/.local/opt/comfyui        # holds ComfyUI/ (clone) and .venv/
python3 scripts/comfy-run.py background photo.png -o cutout.png
python3 scripts/comfy-run.py upscale    photo.png -o 2x.png --factor 2
python3 scripts/comfy-run.py remove     frame.png -o clean.png --rect 1500,60,360,120
python3 scripts/comfy-run.py inpaint    photo.png "what to put there" -o out.png --mask m.png
python3 scripts/comfy-run.py generate   "description" -o still.png --size 1344x768 --seed 7
```

`comfy-run.py` starts the server through `scripts/comfy-serve.sh` when none is
running and stops what it started; pass `--keep` on the first of several jobs
(the first model load is slow). One job at a time on the GPU: the diffusion
model takes about 6 GB in fp8, so a TTS or music model beside it overflows.

## Licenses: the most-cited model is the wrong one

| Task | Use | License | Not | Why |
|---|---|---|---|---|
| Generate / inpaint | Z-Image-Turbo 6B (Tongyi-MAI) | Apache-2.0 | FLUX.1 dev, large FLUX.2 | commercial use needs a paid license |
| Photo upscale | 4xRealWebPhoto_v4_dat2 (Phips) | CC-BY-4.0, credit | 4x-UltraSharp | CC-BY-NC-SA |
| Fast upscale | RealESRGAN_x4plus | BSD-3 | | |
| Background removal | BiRefNet-general | MIT | RMBG-2.0 (BRIA) | CC-BY-NC; commercial only by contract |
| Object removal | big-lama (Samsung) | Apache-2.0 | | |
| Background/LaMa node | ComfyUI-RMBG (1038lab) | GPL-3 (node code) | | does not affect image licenses |

Z-Image Turbo settings: 8 steps, `cfg 1`, `res_multistep` + `simple`,
`ModelSamplingAuraFlow shift 3`, and `ConditioningZeroOut` on the negative
(it does not run without it).

## Removing a logo: LaMa, not diffusion

`remove` (LaMa) rebuilds texture from the surroundings in seconds and invents
nothing. Diffusion inpainting asked for "clear sky" over trees invents objects.
`remove` takes things out; `inpaint` puts something new in with a prompt.

## Fitting 8 GB

- Start the server with `--fp8_e4m3fn-unet` (bf16 converts to fp8 on load);
  the text encoder is `qwen_3_4b_fp8_mixed`.
- Reuse a cached `torch` wheel from another venv via `uv` instead of
  downloading 3 GB again.
- Video upscaling with SeedVR2 does not pay off on 8 GB: hours per minute of
  video, and it invents detail. Use it only to rescue third-party low-res
  footage.

## API format

The JSON the UI saves (`nodes`, `links`, subgraphs) is not what `/prompt`
accepts. The workflows in `workflows/` are API format
(`{"id": {"class_type", "inputs"}}`). Convert a UI template with "Export
(API)"; recent official templates hide nodes inside `definitions.subgraphs`.

Install and model files: [references/install.md](references/install.md).
