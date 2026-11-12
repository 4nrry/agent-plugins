# Batch 2026-11-11-tooling-update — claims

**Notes, not run records.** Why media-agent 0.22.0 changes what five skills
say about the tools under them, after the machine's defaults moved to
FFmpeg 9.0.2, Blender 5.3.0 and ComfyUI 0.45.0. Nothing here compares an agent
with and without a skill. Three kinds of evidence, kept apart below: what was
**run here** on 2026-11-11, what was **read upstream** that day, and what was
**carried over** from earlier notes without being run again.

**Machine.** Linux x86-64, RTX 4070 Laptop (8 GB) beside an integrated Intel
Arc, NVIDIA driver 615.71.09. `ffmpeg` on PATH is the static build
`n9.0.2-49-gc179411bbb-20261111`; the distribution's 8.1.2-2ubuntu2 is
`ffmpeg8`. Blender 5.3.0, 5.2.4 LTS and 5.2.0 LTS from the official tarballs.
Another process held about 5 GB of the GPU throughout, so nothing that needs
the whole card was run.

## Run here

**`drawtext` on FFmpeg 9.0.2.** A 320×180 black frame, white text, one run
each. The 9.0.2 build is configured with `--enable-fontconfig`,
`--enable-libfreetype`, `--enable-libharfbuzz` and `--enable-libass`, like
8.1.2.

| Filter | 9.0.2 | 8.1.2 |
|---|---|---|
| `drawtext=text=Hello:...` (no font given) | exit 234, `impossible to find font information` | exit 0 |
| `drawtext=text=Hello:font=DejaVu Sans:...` | exit 234, same message | not run |
| `drawtext=text=Hello:fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:...` | exit 0, same mean pixel value as 8.1.2 (4.011) | exit 0 |
| no font, `FONTCONFIG_FILE=/etc/fonts/fonts.conf` | exit 234 | not run |
| no font, `FONTCONFIG_PATH=/etc/fonts` | exit 234 | not run |
| `subtitles=s.srt` (libass, font by name) | exit 0, text drawn | exit 0, text drawn |

With `FC_DEBUG=1` the 9.0.2 build read the system's substitution rules and
still matched no font. Why was not found; pointing fontconfig at the system's
configuration did not help, a font file did.

**Animated WebP on FFmpeg 9.0.2.** Input: 12 RGBA frames (a disc moving on
transparency) packed by `cutout_pack.py pack` into a 200×102 animated WebP of
20 KB.

- 9.0.2: `ffmpeg -i anim.webp out/f%04d.png` exit 0, 12 PNGs with four bands
  (alpha plane mean 78.5 on frame 5); `ffprobe -count_frames` reports codec
  `webp_anim`, `argb`, 12 frames.
- 8.1.2: exit 69, no file written, `image data not found` then a decoding
  error.
- `cutout-frames.sh anim.webp work --fps 10` with `COMFY_SERVER` pointed at a
  closed port, so it stops after extraction: with 9.0.2 first on PATH it
  extracted 12 frames and then stopped at the server, exit 1, as designed;
  with 8.1.2 first on PATH it wrote no frame and exited 69 inside ffmpeg.
- Pillow 13 read the same file as 12 frames, RGBA, `is_animated` true.
- `ffmpeg -decoders`: 9.0.2 lists `webp` and `webp_anim`, 8.1.2 only `webp`.
  The skill names the decoder rather than a version, since no other build was
  tried.

**Blender: `use_nodes`.** A probe on 5.2.0, 5.2.4 and 5.3.0, each started with
`--factory-startup`: a new material already has a node tree (`Material
Output`, `Principled BSDF`) and a new world already has one (`Background`,
`World Output`), and `use_nodes` reads `True`. On 5.2.4 and 5.3.0, reading
either property printed `DeprecationWarning: 'Material.use_nodes'` (or
`'World.use_nodes'`) `is expected to be removed in Blender 6.0`; the cold
review saw the same two warnings on 5.2.0, which this probe did not look
for. The scripts
now touch `use_nodes` only when `node_tree` is `None`.

**Blender: the two scripts before and after.** Test model: a rigged glb made
for this run (a subdivided cylinder, two bones, actions `Idle` and `Wave`,
61 KB). `turntable.py --preview --res 540` (3 frames, Cycles) and
`scene_kit.py --demo --frames 8` (EEVEE, preview tier), each with
`--python-exit-code 1`, through the `blender` launcher (offloaded to the
NVIDIA card) unless marked bare.

| Run | turntable | scene_kit demo | deprecation warnings (turntable, scene) |
|---|---|---|---|
| 0.21.1 scripts, 5.3.0 | exit 0, 9.1 s, Cycles on CUDA | exit 0, 1.7 s, 8 frames | 1, 2 |
| 0.22.0 scripts, 5.3.0 | exit 0, 7.1 s, Cycles on CUDA | exit 0, 1.4 s, 8 frames | 0, 0 |
| 0.22.0 scripts, 5.2.4 | exit 0, 7.6 s, Cycles on CUDA | exit 0, 1.8 s, 8 frames | 0, 0 |
| 0.22.0 turntable, 5.3.0, `CYCLES_BACKEND=OPTIX` | exit 0, `cycles device: OPTIX` | | |

- Pixels, 0.21.1 against 0.22.0 on 5.3.0: the scene plates are identical
  (largest difference 0 on frames 1, 4 and 8); the turntable frames differ by
  at most 1 level, mean difference 0.00000 to five decimals. The PNG files
  differ byte for byte either way: Blender writes the render's `Date` into a
  text chunk.
- 5.3.0 against 5.2.4, 0.22.0 scripts: largest difference 1 level in both.
- The three demo figures came out the same in every run: rotation mode `XYZ`,
  faces 0, −π/2 and π, height 1.900, feet at 0.000.
- `check_motion.py` on the 5.3.0 and 5.2.4 plates (run with a Python that has
  numpy and Pillow; the system Python has neither): 8 frames, smallest change
  0.119, median 0.315, no still pair, exit 0.

**Blender: exit code.** A script that raises, on 5.3.0: exit 0 without
`--python-exit-code`, exit 1 with `--python-exit-code 1`. The turntable
command in its skill and docstring now passes the flag.

**Blender: which GPU EEVEE uses.** `gpu.platform` after a 64×64 EEVEE render:

| Run | Backend | Card |
|---|---|---|
| 5.3.0, no offload variables | Vulkan | NVIDIA GeForce RTX 4070 Laptop GPU |
| 5.3.0, `__NV_PRIME_RENDER_OFFLOAD=1` and `__GLX_VENDOR_LIBRARY_NAME=nvidia` | Vulkan | NVIDIA |
| 5.3.0, offloaded with all three variables | Vulkan | NVIDIA |
| 5.2.4, no offload variables | OpenGL | Mesa Intel Arc |

During a 60-frame final-tier demo render, `nvidia-smi` listed the Blender
process for 5.3.0 without offload and for 5.2.4 offloaded, and did not list it
for 5.2.4 without offload. The NVIDIA card was already awake for the other
process; whether Vulkan picks it when the card is suspended was not tested.
An earlier session on the same day reported that 5.3.0 without offload
rendered on the integrated GPU; these runs did not reproduce that, and the
difference was not resolved. The skill keeps the advice to offload and adds
the check.

**ComfyUI environment, checked without running a workflow.** The installed
clone is at tag v0.45.0 (commit `989d93d0d968e704c589ce0146bb18c77f6b50cc`)
with origin `github.com/comfyanonymous/ComfyUI`; its README at the tag is
byte-identical to upstream's. Its virtual environment runs Python 3.12.16 and
torch 2.14.1+cu130, and `.venv/bin/python` is a link to uv's interpreter.
ComfyUI-RMBG is at commit `a66a5e641a54988d80ed6aad18946081c85f309e`
(2026-10-20), whose `pyproject.toml` says 3.3.0; the repository has no tags.
`uv pip compile` (uv 0.13.7) of torch, torchvision, torchaudio and both
`requirements.txt` files resolved for Python 3.13 and for 3.12 (both exit 0).
Nothing was installed and no workflow was run: the GPU was shared.

**Seed-VC environment.** The installed copy: Python 3.10.22, torch and
torchaudio 2.4.0+cu121, clone at `51383efd921027683c89e5348211d93ff12ac2a8`,
environment 5.8 GB and checkpoints 1.8 GB (`du --apparent-size`). Nothing was
converted.

## Read upstream

- `gh api repos/comfyanonymous/ComfyUI` answers with `Comfy-Org/ComfyUI`
  (GPL-3.0). Release v0.45.0, published 2026-11-10, is the latest. Its README,
  section "Manual Install": Python 3.13 "very well supported", 3.12 to try
  when custom node dependencies fail on 3.13, 3.14 works with some custom
  nodes failing; NVIDIA stable torch from `whl/cu130` (pip
  `--extra-index-url`), nightly from `whl/nightly/cu132`; a cu130 or newer
  build required on the 20 series and later. `install.md` keeps uv's
  `--index-url` for the torch line, as before.
- `Plachtaa/seed-vc`: archived, GPL-3.0, last commit `51383ef` on 2025-04-20.
  `inference.py` there: defaults 30 diffusion steps, cfg rate 0.7, length
  adjust 1.0, f0 condition off, fp16 on; the reference is cut to 25 s; without
  f0 it loads `DiT_seed_v2_uvit_whisper_small_wavenet_bigvgan_pruned.pth` and
  works at 22.05 kHz; no random seed is set. The Hugging Face card
  `Plachta/Seed-VC` declares `gpl-3.0` and holds that checkpoint.
- SeedVR2: `ByteDance-Seed/SeedVR` Apache-2.0; `ByteDance-Seed/SeedVR2-3B`
  and `-7B` cards `apache-2.0`; the node `numz/ComfyUI-SeedVR2_VideoUpscaler`
  Apache-2.0, latest release v2.5.23 (2025-12-24), whose `inference_cli.py`
  has every flag listed in `models.md`; `cmeka/SeedVR2-GGUF` card
  `apache-2.0`, with `seedvr2_ema_3b-Q8_0.gguf`.
- `ResembleAI/chatterbox` card `mit`; it holds both `s3gen.pt` and
  `s3gen.safetensors`. In the `chatterbox-tts` 0.1.7 package (installed copy):
  the multilingual TTS downloads `s3gen.pt`, `ChatterboxVC.from_pretrained`
  downloads `s3gen.safetensors` and `conds.pt`, and both load into the same
  `S3Gen` class. The repository's tree lists `s3gen.pt` at 1,057,165,844
  bytes and `s3gen.safetensors` at 1,056,484,620; whether they hold the same
  weights was not checked (it needs the download).

## Carried over, not run here

Each of these is in the plugin marked as carried over, with its source.

- **ComfyUI 0.45.0 workflows**: `comfy-run.py background`, `remove` and
  `upscale` passing on 0.45.0 with ComfyUI-RMBG 3.3.0, and `generate` and
  `inpaint` not run there. Source: the audit of the machine's media tooling
  on 2026-11-11 by another session.
- **SeedVR2 on 8 GB**: fit only as 3B GGUF Q8 with block swap and 512 px VAE
  tiles; batches of 33 frames ran out of memory, the run used 9; 36 frames
  540p to 1080p in 292 s (about 8 s a frame), peaks 7.8 GB VRAM and 10 GB
  RAM; SSIM 0.65 against 0.84 for bicubic. Source: the notes of the media
  toolbox SeedVR2 was removed from on 2026-09-23.
- **Seed-VC recipe**: the pinned commit, checkpoint, steps, cfg, fp16 off and
  seed 42 come from the same notes; each value except the seed and fp16 was
  checked against upstream `inference.py` above. About 4 s per short line on
  an RTX 4070 Laptop after about 40 s of loading: same notes.
- **Speaker similarity**, measured 2026-11-03 with Chatterbox's speaker
  encoder: Seed-VC 0.81–0.93, ChatterboxVC 0.74–0.91, ElevenLabs voice changer
  about 0.84–0.87. Source: same notes. They give neither the number of lines
  nor the voices.
- **ChatterboxVC from the multilingual `s3gen.pt`** with no extra download:
  same notes; the code paths above were read, not run.

The licence table in `image-retouching/references/models.md` already held
every accepted and rejected model of those notes (Z-Image-Turbo,
4xRealWebPhoto, RealESRGAN, BiRefNet, big-lama, the RMBG node; 4x-UltraSharp,
RMBG-2.0, FLUX.1 dev), as did the TTS table in `voice/references/tts.md`.
This batch adds SeedVR2 (a row and a section in `models.md`) and Seed-VC (the
new `voice/references/voice-conversion.md`).

## Cold review

A subagent read the diff without this record's conclusions and re-checked the
upstream facts and the runs on this machine. It confirmed the upstream
facts, the `drawtext`, libass and animated WebP results, the `use_nodes`
probe, both scripts on 5.3.0 and 5.2.4, the exit codes and the GPU table. It
did not re-run the pixel and timing tables, `check_motion.py` or OptiX. Its
findings, all applied: the ComfyUI workflow results in `install.md` lacked the
carried-over marker; `3d-scenes` stated the Vulkan observation without its
caveat; `video-editing` generalised one build to "static ones"; the
animated-WebP requirement named a version in a `SKILL.md` body; the
ChatterboxVC note omitted `conds.pt` and the size difference; the similarity
table did not say the encoder is one contestant's.
