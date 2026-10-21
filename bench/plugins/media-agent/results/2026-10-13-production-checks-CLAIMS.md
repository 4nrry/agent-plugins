# Batch 2026-10-13-production-checks — claims

**Notes, not run records.** Imported from the media-agent README and skills
(0.1.0–0.4.1), measured during one real production (a 64 s institutional
video with pt-BR voice-over, generated music, stock b-roll, a Blender product
turntable and a Remotion render, delivered in 16:9, 1:1, 9:16, 4:5 and a PDF
carousel, on an 8 GB RTX 4070 Laptop). n=1 per item. They support "this
behaves as described"; they support no claim that the skills improve an
agent's outcomes, which would need paired arms.

**Audio**
- `vo-normalize.sh` on three real sentences (Pocket TTS at -24.4 and -28.5
  LUFS, ElevenLabs at -16.8): `loudnorm` alone delivered -17.3 asking -16, in
  one pass or two; with the corrective pass, -16.1, -16.2 and -16.0 by
  `ebur128`.
- Kinocut 1.15.1 `normalize-audio` took a voice from -28.6 to -16.5 LUFS; its
  MCP server listed 196 tools; `sound-qa-loudness` accepted no arguments and
  only printed usage; `info`, `trim` (15.000 s) and the structured
  missing-file error worked.
- ElevenLabs (Starter): 2 SFX, one 15 s music clip, 2 isolations and 1
  transcription cost about 290 credits by balance difference. One MCP SFX cost
  16.7 credits against an `estimate_only` of 50; the MCP estimated Seedream 5
  Pro at ~818 credits per image and Veo 3.1 Fast at ~7,272 per clip. `stt`
  turned "vinte mil reais" into "R$ 20 mil".
- Four local TTS engines were rejected by a native pt-BR listener (2026-09).

**Image and video**
- `grok-image.sh` still 1280x720 in 64 s; `agy-image.sh` 1376x768 in
  100–175 s; `grok-video.sh --image` 6 s at 736x400 in 84 s (`--res 720p`:
  1280x704 in 86 s); `veo.py --image` 8 s at 1920x1080 in 109 s, keeping the
  still's composition, while text-only Veo ignored the requested framing.
- 2026-10-13, same dawn-windrow still: `nano.py gemini-nano-banana-2.1` 12 s,
  1376x768; `gemini-3-pro-image --image` 17 s, kept framing but overdid the
  edit ("steam" became flames); Veo Lite 720p in 44 s, faithful; Veo Standard
  1080p in 107 s, broke the windrows into separate mounds; Veo Lite rejected
  `negativePrompt` (HTTP 400); Veo Standard 1080p refused `--seconds 4`.
- Upscaling a Grok 480p clip with DAT2: ~9.5 s per frame (23 min for 6 s).
- SeedVR2 3B GGUF Q8 on 8 GB: 36 frames 540p→1080p in 292 s, 7.8 GB VRAM peak,
  10 GB RAM; batch of 33 frames ran out of memory; SSIM 0.65 vs 0.84 for
  bicubic against the real 1080p.

**Retouching and 3D**
- `comfy-run.py` ran all five workflows against a real ComfyUI; a `--rect`
  mask built in the graph matched a PNG mask pixel for pixel
  (`magick compare -metric AE` = 0). Diffusion inpainting "clear sky" over
  trees produced colored sheds in 60 s; LaMa took 3 s.
- `turntable.py`: 120 frames of a real glb in CUDA on Blender 5.2, ~6 min at
  900 px and 128 samples. `glb-turntable.tsx`: the same 120 frames in ~7 s with
  `--gl=angle`; `--gl=swangle` rendered empty frames.
- ECharts inside Remotion needed ~1.5 s of `delayRender` per frame.

**Licenses** were read on Hugging Face, OpenModelDB and GitHub on 2026-09-21.
