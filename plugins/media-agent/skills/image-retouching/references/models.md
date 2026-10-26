# Models and their licenses

Checked against the model cards on 2026-10-26. Check again before company
work: licenses change between releases.

| Task | Use | License | Not | Why not |
|---|---|---|---|---|
| Generate, inpaint | Z-Image-Turbo 6B (Tongyi-MAI) | Apache-2.0 | FLUX.1 dev, FLUX.2 dev, FLUX.2 klein 9B | non-commercial licenses |
| Generate, alternative | FLUX.2 klein 4B | Apache-2.0 | FLUX.3 Klein | its license allows commercial output only under US$5M revenue; ~25 GB VRAM |
| Photo upscale | 4xRealWebPhoto_v4_dat2 (Phips) | CC-BY-4.0, credit | 4x-UltraSharp | CC-BY-NC-SA |
| Fast upscale | RealESRGAN_x4plus | BSD-3 | | |
| Background removal | BiRefNet-general | MIT | RMBG-2.0 (BRIA) | gated, non-commercial license; commercial only by contract |
| Object removal | big-lama (Samsung) | Apache-2.0 | | |
| Background and LaMa nodes | ComfyUI-RMBG (1038lab) | GPL-3 (node code) | | does not affect the images' license |

The bundled workflows use Z-Image Turbo; FLUX.2 klein 4B has not been run with
them.

## Z-Image Turbo settings

8 steps, `cfg 1`, `res_multistep` with `simple`, `ModelSamplingAuraFlow`
shift 3, and `ConditioningZeroOut` on the negative (it does not run without
it). On 8 GB: the diffusion model in fp8 (`--fp8_e4m3fn-unet`, NVIDIA only)
and the `qwen_3_4b_fp8_mixed` text encoder.
