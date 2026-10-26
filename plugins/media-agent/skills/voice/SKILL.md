---
name: voice
description: Produces edit-ready voice-over with any TTS — one sentence per file, spoken text apart from captions, -16 LUFS, a durations JSON for captions and ducking. Use for narration, TTS, pt-BR speech, loudnorm, synced captions, a quiet or mispronounced voice, or a named TTS (ElevenLabs, Kokoro).
---

# Voice-over

Loudness, pronunciation and licensing fail silently and show up only at
delivery. These rules hold for any TTS; the engines and their traps are in
[references/tts.md](references/tts.md).

## One sentence per file, one JSON that drives everything

```json
[{"id": "s1", "text": "Each report costs up to 20k.", "say": "Each report costs up to twenty thousand.",
  "duration": 6.87, "start": 0.9}]
```

- `text` is the caption; `say` is what the TTS speaks. Acronyms, brand names
  and numbers are written one way and spoken another: spell them out in `say`.
- `duration` comes from the generated file (`ffprobe`), never an estimate.
  Captions and music ducking derive from it.
- Captions built from this JSON have no transcription errors. Use
  speech-to-text only for audio you did not generate (`audio` skill).

## Loudness

TTS output is usually well below -16 LUFS (local engines landed at -24 to
-30), and music at -20 buries it. Normalize every sentence to -16 LUFS
(-1.5 dBTP), then the final video again. From this skill's directory:

```bash
scripts/vo-normalize.sh -o vo-norm -j vo-durations.json vo/*.wav
ffmpeg -i final.raw.mp4 -c:v copy -af loudnorm=I=-16:TP=-1.5:LRA=11 -c:a aac -b:a 192k final.mp4
```

The script measures in two passes and adds a limiter pass, because the
true-peak ceiling makes `loudnorm` land 1–2 LU short on short speech. Duck the
music under the voice from 0.5 to about 0.16 with a ~0.35 s ramp.

## Choosing the engine

- Language first: a model can read Portuguese with an English or European
  accent. Let a native speaker listen before choosing; metrics do not replace
  that.
- License second: the weights' license, or the plan's terms for a cloud
  service, must allow commercial use.
- Then where it runs: CPU, an 8 GB GPU, or the cloud.

## Real people's voices

Do not synthesize or clone the voice of a real person who appears in the video
unless they record it or authorize it. First-person on-screen text with their
photo works; if they want narration, they record it and the same pipeline
applies.

## API keys

Keys come from the environment, never from a repo file or the command line
(`ps` shows it). A secrets manager's `run` (bws, 1Password, sops) injects them
into the child process only. `bws run` joins arguments into one shell string:
re-quote a prompt with spaces (`printf '%q '`).
