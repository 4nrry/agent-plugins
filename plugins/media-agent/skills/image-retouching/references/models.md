# Models and their licenses

Checked against the model cards on 2026-10-26, the SeedVR2 row on
2026-11-11. Check again before company work: licenses change between
releases.

| Task | Use | License | Not | Why not |
|---|---|---|---|---|
| Generate, inpaint | Z-Image-Turbo 6B (Tongyi-MAI) | Apache-2.0 | FLUX.1 dev, FLUX.2 dev, FLUX.2 klein 9B | non-commercial licenses |
| Generate, alternative | FLUX.2 klein 4B | Apache-2.0 | FLUX.3 Klein | its license allows commercial output only under US$5M revenue; ~25 GB VRAM |
| Photo upscale | 4xRealWebPhoto_v4_dat2 (Phips) | CC-BY-4.0, credit | 4x-UltraSharp | CC-BY-NC-SA |
| Fast upscale | RealESRGAN_x4plus | BSD-3 | | |
| Background removal | BiRefNet-general | MIT | RMBG-2.0 (BRIA) | gated, non-commercial license; commercial only by contract |
| Object removal | big-lama (Samsung) | Apache-2.0 | | |
| Background and LaMa nodes | ComfyUI-RMBG (1038lab) | GPL-3 (node code) | | does not affect the images' license |
| Video upscale, rescue only | SeedVR2 3B (ByteDance), through the `numz/ComfyUI-SeedVR2_VideoUpscaler` node | Apache-2.0 (code, weights, node, and the `cmeka/SeedVR2-GGUF` files) | | not installed; see below |

The bundled workflows use Z-Image Turbo; FLUX.2 klein 4B has not been run with
them.

## Z-Image Turbo settings

8 steps, `cfg 1`, `res_multistep` with `simple`, `ModelSamplingAuraFlow`
shift 3, and `ConditioningZeroOut` on the negative (it does not run without
it). On 8 GB: the diffusion model in fp8 (`--fp8_e4m3fn-unet`, NVIDIA only)
and the `qwen_3_4b_fp8_mixed` text encoder.

## Video upscaling on 8 GB: SeedVR2

Carried over, not re-run: one run on an RTX 4070 Laptop (8 GB), from the
notes of the media toolbox it was removed from on 2026-09-23.

- It fit only as the 3B model quantized to GGUF Q8
  (`seedvr2_ema_3b-Q8_0.gguf`), with the DiT's blocks swapped out to the CPU
  and the VAE encoding and decoding in 512 px tiles. The run used batches of
  9 frames; batches of 33 ran out of memory.
- 36 frames from 540p to 1080p took 292 s, about 8 s a frame, with peaks of
  7.8 GB of VRAM and 10 GB of RAM: hours for one minute of video.
- Scored against the real 1080p frames, SSIM was 0.65 for SeedVR2 and 0.84
  for plain bicubic scaling. It invents detail, so it is for third-party
  footage that only exists at low resolution, never for footage that already
  is 1080p.
- The settings as flags of the node's `inference_cli.py`, all present at its
  release v2.5.23: `--dit_model seedvr2_ema_3b-Q8_0.gguf --resolution 1080
  --batch_size 9 --uniform_batch_size --temporal_overlap 2 --blocks_to_swap 32
  --swap_io_components --dit_offload_device cpu --vae_offload_device cpu
  --vae_encode_tiled --vae_decode_tiled`, with 512 for both tile sizes and 64
  for both tile overlaps.
