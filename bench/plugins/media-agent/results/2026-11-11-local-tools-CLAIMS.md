# Batch 2026-11-11-local-tools — claims

**Notes, not run records.** Why media-agent 0.24.0 ships the scripts that run
the local voice engines, a ComfyUI `edit` command on FLUX.2 klein 4B, and a
ranking of the TTS engines by ear. Until now the scripts lived only in the
machine's media toolbox, beside each engine's environment. The machine's owner
decided the plugin is their home. Nothing here compares an agent with and
without a skill. Three kinds of evidence, kept apart: **run here**, **read
upstream** and **carried over**.

**Machine.** Linux x86-64, RTX 4070 Laptop (8 GB), ComfyUI 0.45.0 with torch
2.14.1+cu130. Each engine has its own environment: Kokoro (Python 3.12),
Qwen3-TTS (3.12), Chatterbox (3.11, chatterbox-tts 0.1.7), Seed-VC (3.10,
torch 2.4.0+cu121). Another session rendered in Blender in bursts, so GPU
jobs started with the card under 1.3 GB in use. No model was downloaded:
the Hugging Face cache already held every file, and the Chatterbox and
Seed-VC runs set `HF_HUB_OFFLINE=1`; the Qwen run could not (the package
queries the hub), and the model's cache folder kept its size.

## Run here

**The four voice scripts**, each with the Python of its engine's environment,
on "O relatório custa até vinte mil reais e sai em três dias.":

| Script | Result | Against the toolbox's own wrapper |
|---|---|---|
| `kokoro-tts.py --voice pm_alex` | 3.8 s of speech in 35 s, CPU | same length; samples differ by up to 0.08, less than two runs of the old wrapper differ from each other (0.14): Kokoro is not deterministic |
| `kokoro-tts.py --voice af_heart` | failed: the English G2P tried to install a spaCy model into the environment and could not | not run |
| `kokoro-tts.py --voice alex` | exit 1, `not a Kokoro voice name` | |
| `qwen-tts.py --seed 7` (VoiceDesign 1.7B) | 4.5 s in 22 s | the old wrapper has no seed: not compared |
| `chatterbox-tts.py --seed 7` (v2) | 4.1 s in 63 s with the load | the old wrapper has no seed: not compared |
| `chatterbox-tts.py --model pt-br --source <upstream src> --seed 7` | 3.8 s in 72 s with the load | the pt-BR launcher, same seed: same length, samples within 0.00003 |
| `seed-vc.py REF OUTDIR line1 line2` (reference: the v2 take) | both lines, 112 s with the load; 3.800 s in, 3.796 s out, 22.05 kHz | the old batch wrapper on the same files: identical samples (largest difference 0) |

The upstream source given to `--model pt-br` was `resemble-ai/chatterbox` at
`ab55923c27757c90cfcc407baa57dc25a7d25217`. The pack's files resolved from
the cache at the revisions the script pins. Each script's `--self-test` runs
on the system Python with none of the packages, under `just check`.

**`comfy-run.py edit`**, through `comfy-serve.sh` on a free port, the
server kept up across jobs and stopped after:

- `generate` (Z-Image Turbo) made the source, 1024×576, 87 s of job after
  about 70 s of server start.
- Three edits with seed 7: add a succulent in a white pot left of the mug;
  remove the mug; make the mug matte navy blue. Each did what was asked and
  kept the table, window and light (viewed on a contact sheet). Jobs of 46 s
  (model load), 12 s and 15 s. Peak VRAM over the whole series, sampled
  every 0.5 s: 7,668 MiB. Output 1360×768.
- Pixels away from the change, after scaling each edit back to 1024×576:
  mean differences of 7.3, 7.3 and 8.4 levels over the window, 6.0, 2.6 and
  3.1 over a table corner; 26 %, 41 % and 40 % of all pixels moved by more
  than 8 levels. Hence the rule that `edit` is for generated stills.
- `edit` with a missing image exits 1 with `image not found`.

## Read upstream

- `black-forest-labs/FLUX.2-klein-4b-fp8`: Apache-2.0, not gated; its
  `flux-2-klein-4b-fp8.safetensors` (4,070,624,520 bytes) has the same sha256
  as the installed file. `Comfy-Org/Flux-2-Klein-4B`
  `split_files/vae/flux2-vae.safetensors` has the same sha256 as the
  installed VAE.
- `resemble-ai/chatterbox` README at `ab55923`: "As of August 2026,
  Chatterbox is retired research and is no longer maintained"; the Single
  Language Pack lists `ResembleAI/Chatterbox-Multilingual-pt-br`, whose card
  says MIT and holds `t3_pt_br.safetensors`, `s3gen_v3.pt` and its grapheme
  file. The source's `from_local` takes a `t3_model` file name; 0.1.7's does
  not. There is no loader for a language pack, hence the folder the script
  links together.
- `ace-step/ACE-Step-1.5` README: the quick start runs `uv run acestep`
  (Gradio) or `uv run acestep-api`; `cli.py` is still in the repository.

## Carried over, not run here

From the notes on the machine's tooling of 2026-11-11, written by the
session that ran these tests first:

- The listening verdict on three pt-BR sentences, v2 against the pt-BR pack,
  same seed and built-in voice: the pack slightly better; no local engine
  better than ElevenLabs or Gemini TTS Flash for pt-BR; local engines good in
  English. No side-by-side with the cloud.
- Whisper large-v3-turbo transcribed those six takes without a word wrong.
- The pack loads in 10.6 s and holds 3.27 GB of VRAM (v2: 3.30 GB).
- FLUX.2 klein text-to-image at 4 steps drew a two-handled mug on 2 of 3
  seeds where Z-Image Turbo did not.
- ACE-Step through the launcher: 10.0 s of 48 kHz stereo in 154 s, after the
  toolbox moved.

**What should call what.** The toolbox's launchers (`kokoro-tts`, `qwen-tts`,
`chatterbox-tts`, `chatterbox-ptbr`, `seed-vc`, `seed-vc-batch`) still call
the toolbox's copies of these scripts. Repointing them is outside this
repository; the mapping is in the hand-over note for the owner.
