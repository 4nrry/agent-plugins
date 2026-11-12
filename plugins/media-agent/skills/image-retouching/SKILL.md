---
name: image-retouching
description: Retouches images on your own GPU with commercially licensed models — background removal, upscaling, removing a logo or object, masked inpainting, editing a still by instruction, stills generated locally. Use for a transparent PNG, upscale, removing an overlay from your own image, inpainting with a mask, an edit described in words, ComfyUI or VRAM limits, or a model like FLUX, Z-Image, RMBG, BiRefNet or LaMa.
---

# Image retouching

## Rules for any model

- **License of the weights first.** The most-cited model for a task is often
  non-commercial. Check the model card before it touches company work; the
  models this skill uses, and the popular ones to avoid, are in
  [references/models.md](references/models.md).
- **Removing is not inpainting.** To take something out (a logo, a sign, a
  watermark), use a texture-fill model such as LaMa: it rebuilds the
  surroundings and invents nothing. Diffusion inpainting asked for "clear sky"
  over trees invents objects. Use prompted inpainting only to put something
  new in.
- **Editing by instruction redraws the whole picture.** `edit` takes a
  sentence and no mask ("remove the mug", "make the mug navy") and keeps the
  scene to the eye, but every pixel is regenerated at about one megapixel.
  Use it on generated stills. On a real photo or a frame whose untouched
  pixels must stay, use `remove` or `inpaint` with a mask.
- **One GPU job at a time** on an 8 GB card: a diffusion model in fp8 takes
  about 6 GB and `edit` nearly all 8, so a TTS or music model beside it
  overflows. Check `nvidia-smi` first: another process on the card is enough.
- **Video upscaling** does not pay off on 8 GB (hours per minute of video, and
  it invents detail). Use it only to rescue third-party low-resolution footage;
  what fit and what it cost are in [references/models.md](references/models.md).

## With the bundled ComfyUI scripts

ComfyUI is an HTTP server; the UI is one client. `scripts/comfy-run.py` starts
the server through `scripts/comfy-serve.sh` when none is running, posts an
API-format graph from `workflows/`, waits on `/history`, downloads the result
and stops what it started. From this skill's directory:

```bash
export COMFY_HOME=~/.local/opt/comfyui        # holds ComfyUI/ (clone) and .venv/
python3 scripts/comfy-run.py background photo.png -o cutout.png
python3 scripts/comfy-run.py upscale    photo.png -o 2x.png --factor 2
python3 scripts/comfy-run.py remove     frame.png -o clean.png --rect 1500,60,360,120
python3 scripts/comfy-run.py inpaint    photo.png "what to put there" -o out.png --mask m.png
python3 scripts/comfy-run.py generate   "description" -o still.png --size 1344x768 --seed 7
python3 scripts/comfy-run.py edit       still.png "remove the mug" -o edited.png --seed 7
```

Pass `--keep` on the first of several jobs; the first model load is slow. It
prints the server's PID: `kill` it after the last job, since later jobs never
stop a server they did not start and it holds the GPU until then.

- The JSON the UI saves (`nodes`, `links`, subgraphs) is not what `/prompt`
  accepts. The workflows here are API format (`{"id": {"class_type",
  "inputs"}}`); convert a UI template with "Export (API)". Recent official
  templates hide nodes inside `definitions.subgraphs`.
- Fit 8 GB: start the server with `--fp8_e4m3fn-unet` (bf16 converts to fp8 on
  load) and reuse a cached `torch` wheel through `uv`.

Install and model files: [references/install.md](references/install.md).
