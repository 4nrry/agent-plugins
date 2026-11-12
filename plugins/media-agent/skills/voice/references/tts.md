# TTS engines

Checked against the vendors' docs and model cards on 2026-10-26, the
Chatterbox rows on 2026-11-11. Check the license and the plan's terms again
before a commercial piece.

## Contents
- The engines
- Which one, by ear
- Running the local engines
- xAI through Hermes
- ElevenLabs

## The engines

A subscription route spends the plan's quota and nothing more; an API-key
route bills every call to that key. Prefer the subscription routes when the
key's budget belongs to something else.

| Engine | Billed to | Runs on | License | Trap |
|---|---|---|---|---|
| ElevenLabs | ElevenLabs plan credits | cloud | paid plan for commercial use | best pt-BR by a margin among the paid APIs |
| xAI TTS, voice `liora`, through Hermes | Grok subscription | cloud | xAI's terms | `scripts/hermes-tts.sh "text" s1.mp3`; mp3 24 kHz mono at about -20 LUFS, so normalize it like the rest |
| Pocket TTS (Kyutai) | nothing (local) | CPU, `uv tool install pocket-tts` | code MIT, weights CC-BY-4.0 (credit) | without `--language portuguese` Portuguese comes out as accented English; larger `_24l` variants exist |
| Kokoro-82M | nothing (local) | CPU | Apache-2.0 | pins Python below 3.13: `uv venv -p 3.12`; English voices need the English G2P (`misaki[en]` and a spaCy model) |
| Qwen3-TTS 1.7B | nothing (local) | 8 GB GPU | Apache-2.0 | Portuguese sounds European; `--instruct` does not fix it |
| Chatterbox Multilingual (v2) | nothing (local) | 8 GB GPU, Python 3.11 | MIT | the `perth` watermarker is `None` in some builds: fall back to the dummy one; upstream calls Chatterbox retired research, no longer maintained, since August 2026 |
| Chatterbox, Brazilian Portuguese pack | nothing (local) | 8 GB GPU, about 3.3 GB (carried over) | MIT | `ResembleAI/Chatterbox-Multilingual-pt-br`; chatterbox-tts 0.1.7 from PyPI cannot load it, it needs the upstream source |
| Gemini TTS (`gemini-3.8-flash-tts`) | Gemini API key, per use | cloud, Gemini API | Gemini API terms | not tried yet |

## Which one, by ear

Carried over, not re-run here: on 2026-11-11 one listener (the plugin's
maintainer) compared three pt-BR sentences in the built-in voice, with the
same seed, on Chatterbox v2 and the pack, without a side-by-side against the
cloud. The verdict, recorded in that day's notes on the machine's tooling:

- The Brazilian Portuguese pack sounds slightly better than Chatterbox v2.
- No local engine reads Brazilian Portuguese as well as ElevenLabs or Gemini
  TTS Flash. Final pt-BR narration goes to one of those.
- In English the local engines are good: try them first.

So: pt-BR narration that ships through a cloud TTS; the pt-BR pack for drafts,
work without a network and cloned voices; English local first. In the same
notes Whisper large-v3-turbo transcribed the six test takes without a word
wrong, so the difference is accent and prosody, which only listening judges.

## Running the local engines

Each script in `scripts/` runs under the Python of its own environment, never
the system's, because each engine pins its own torch. From the voice skill's
directory, with the environment's Python as `python`:

| Script | Environment | Measured on an RTX 4070 Laptop (8 GB) |
|---|---|---|
| `kokoro-tts.py "text" -o out.wav [--voice pm_alex]` | `uv venv -p 3.12`, then `uv pip install kokoro soundfile` | 3.8 s of speech in 35 s on the CPU, model load included |
| `qwen-tts.py "text" -o out.wav [--instruct "..."] [--clone ref.wav --ref-text "..."] [--seed N]` | `uv venv -p 3.12`, then `uv pip install qwen-tts torch soundfile` | 4.5 s of speech in 22 s, model already cached |
| `chatterbox-tts.py "text" -o out.wav [--ref voice.wav] [--seed N]` | `uv venv -p 3.11`, then `uv pip install chatterbox-tts` | v2: 4.1 s of speech in 63 s with the load |
| `chatterbox-tts.py ... --model pt-br --source SRC` | the same, plus a checkout of `resemble-ai/chatterbox` newer than 0.1.7; SRC is its `src/` | 3.8 s of speech in 72 s with the load |
| `seed-vc.py REF.wav OUTDIR a.wav [b.wav ...]` | see [voice-conversion.md](voice-conversion.md) | two lines in 112 s with the load |

- The first run of each model downloads it into the Hugging Face cache.
  `--model pt-br` fetches the pack's three files and three from the base
  Chatterbox model at pinned revisions, about 3 GB.
- A machine can wrap each script and its environment in a launcher on PATH
  (for example `kokoro-tts` running `kokoro-tts.py` with the Kokoro
  environment). The arguments are the same.
- Kokoro is not deterministic: two runs of the same line differ in the
  waveform, not in length.
- `--seed` makes a Chatterbox take repeatable on the same machine: two
  scripts loading the same pack with the same seed gave the same 3.8 s line,
  samples within 0.00003.

## xAI through Hermes

Hermes reaches xAI's TTS with the subscription's OAuth login; its config holds
the voice and language (`tts.provider: xai`, `tts.xai.voice_id: liora`,
`language: pt-BR`). The script runs the official `hermes` CLI and copies the
file it writes to `~/.hermes/cache/audio/`; never reuse Hermes's token in
another tool. xAI's own API (`POST /v1/tts`) takes an API key instead.

## ElevenLabs

- The free plan is non-commercial; company video needs Starter or above.
- Voice Library voices through the API return `paid_plan_required` on Free.
- `mp3_44100_192` needs Creator or above; on Starter use `mp3_44100_128`.
- For pt-BR use `eleven_multilingual_v2`, sending `say` as the request text:
  it is the model that lists Brazilian Portuguese and is documented as the
  most stable for long-form. `eleven_v4` is newer; let a native speaker
  compare before switching.
- Check the credit balance before a batch with the `audio` skill's
  `scripts/eleven.py credits`.
