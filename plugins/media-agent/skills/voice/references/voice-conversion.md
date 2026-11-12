# Voice conversion

A voice-conversion model takes a spoken line and a reference recording and
returns the line in the reference's timbre, keeping its timing, pauses and
intonation. It gives a recurring character one fixed voice whatever reads the
lines: any TTS, or a person who records them. The reference must be a voice
you may use: the skill's rule on real people's voices holds for it.

## Seed-VC v1

Read on 2026-11-11 in the upstream repository and model card. Code and
weights are GPL-3.0 (`Plachtaa/seed-vc`, `Plachta/Seed-VC`). That allows
commercial use; the GPL binds whoever distributes the code, not the audio it
makes ([GPL FAQ](https://www.gnu.org/licenses/gpl-faq.html#GPLOutput)). The
repository is archived, so the recipe pins its last commit.

| Setting | Value | Where it comes from |
|---|---|---|
| Code | `Plachtaa/seed-vc` at `51383ef` (2025-04-20) | the repository's last commit |
| Checkpoint | `DiT_seed_v2_uvit_whisper_small_wavenet_bigvgan_pruned` | what `inference.py` loads with `--f0-condition False`: the v1 model without pitch conditioning, 22.05 kHz |
| `--diffusion-steps` | 30 | upstream default |
| `--inference-cfg-rate` | 0.7 | upstream default |
| `--length-adjust` | 1.0 | upstream default; keeps the timing |
| `--f0-condition` | False | upstream default |
| `--fp16` | False | upstream default is True |
| Seed | 42, set for Python, NumPy and torch before the call | `inference.py` sets none, so without it two runs can differ |
| Reference | the first 25 s | `inference.py` cuts the reference there; a longer one adds nothing |

`scripts/seed-vc.py` applies the recipe: it loads the models once, converts
each line with seed 42 and writes `OUTDIR/<line name>.wav`:

```bash
git clone https://github.com/Plachtaa/seed-vc && git -C seed-vc checkout 51383efd921027683c89e5348211d93ff12ac2a8
uv venv -p 3.10 .venv && uv pip install -p .venv/bin/python torch==2.4.0 torchaudio==2.4.0 --index-url https://download.pytorch.org/whl/cu121
uv pip install -p .venv/bin/python -r <voice skill>/references/seed-vc-requirements-lock.txt
SEED_VC_REPO=$PWD/seed-vc .venv/bin/python <voice skill>/scripts/seed-vc.py REF.wav out/ line1.wav line2.wav
```

The lock file holds the versions of the environment the recipe was set up
in, torch aside. An installed copy, checked on 2026-11-11: Python 3.10.22,
torch and torchaudio 2.4.0+cu121, an environment of 5.8 GB, and 1.8 GB of
checkpoints that the first run downloaded into the clone. There, the script
gave the same samples as the toolbox's own wrapper for two lines (largest
difference 0), each 3.800 s in and 3.796 s out.

Carried over, not re-run: a short line converts in about 4 s on an RTX 4070
Laptop after about 40 s of model loading (the notes of the media toolbox this
recipe was set up in).

## How close each converter gets

Carried over, not re-run: measured on 2026-11-03 on an RTX 4070 Laptop and
recorded in the media toolbox's notes. Each converted line was scored against
its reference recording with the speaker encoder that ships with Chatterbox;
higher is closer.

| Converter | Similarity to the reference |
|---|---|
| Seed-VC v1, the recipe above | 0.81 to 0.93 |
| ChatterboxVC (MIT) | 0.74 to 0.91 |
| ElevenLabs voice changer (cloud) | about 0.84 to 0.87 |

The ranges overlap, and the notes record neither how many lines nor which
voices; they ranked Seed-VC first. The encoder belongs to one of the
contestants, which may favour ChatterboxVC. A score is not a listener: let a
native speaker compare before choosing.

Where the multilingual Chatterbox TTS is already installed, the same notes
ran ChatterboxVC with no extra download by loading that model's `s3gen.pt`.
Read in the `chatterbox-tts` 0.1.7 source, not run: `ChatterboxVC` wraps an
`S3Gen`, the multilingual TTS loads its `S3Gen` from `s3gen.pt`, and
`ChatterboxVC.from_pretrained` downloads `s3gen.safetensors` and `conds.pt`
instead. The two `s3gen` files differ in size (1,057,165,844 and
1,056,484,620 bytes on `ResembleAI/chatterbox`), so they may not hold the same
weights; nobody compared them.
