---
name: voice-over
description: Generates voice-over for video with local TTS (Pocket TTS, Kokoro, Qwen3-TTS, Chatterbox) or ElevenLabs and makes it ready to edit — one sentence per file, -16 LUFS, durations in a JSON that drives the captions. Use when a task involves narration, dubbing, voice-over, TTS, pt-BR speech, LUFS, loudnorm, synced captions, ducking the music, or when the voice "came out quiet", "disappears behind the music" or mispronounced an acronym.
---

# Voice-over for video

Loudness, pronunciation and licensing all fail silently and show up only at
delivery.

## 1. One sentence per file, one JSON that drives everything

```json
[{"id": "s1", "text": "Each report costs up to 20k.", "say": "Each report costs up to twenty thousand.",
  "duration": 6.87, "start": 0.9}]
```

- `text` is the caption; `say` is what the TTS speaks. Acronyms, brand names
  and numbers are written one way and spoken another — spell them out in `say`.
- `duration` comes from the generated file (`ffprobe`), never an estimate.
  Captions and music ducking derive from it.
- Captions built from this JSON have no transcription errors. Use speech-to-text
  only for audio you did not generate.

## 2. Loudness

Local TTS lands around -24 to -30 LUFS; music at -20 buries it. Normalize
every sentence to -16 LUFS (-1.5 dBTP), then the final video again. From this
skill's directory:

```bash
scripts/vo-normalize.sh -o vo-norm -j vo-durations.json vo/*.wav
ffmpeg -i final.raw.mp4 -c:v copy -af loudnorm=I=-16:TP=-1.5:LRA=11 -c:a aac -b:a 192k final.mp4
```

The script measures in two passes and adds a third limiter pass, because the
true-peak ceiling makes `loudnorm` land 1–2 LU short on short speech. Duck the
music under the voice from 0.5 to about 0.16 with a ~0.35 s ramp.

## 3. Which TTS

| Tool | Runs on | License | Trap |
|---|---|---|---|
| Pocket TTS (Kyutai) | CPU, `uv tool install pocket-tts` | code MIT, weights CC-BY-4.0 (credit) | without `--language portuguese_24l` Portuguese comes out accented English |
| Kokoro-82M | CPU | Apache-2.0 | pins Python < 3.13: `uv venv -p 3.12` |
| Qwen3-TTS 1.7B | 8 GB GPU | Apache-2.0 | Portuguese sounds European; `--instruct` does not fix it |
| Chatterbox Multilingual | 8 GB GPU, Python 3.11 | MIT | `perth` watermarker is `None` in some builds: fall back to the dummy one |
| ElevenLabs | cloud | paid plan for commercial use | best pt-BR by a margin |

ElevenLabs specifics:

- The free plan is non-commercial; company video needs Starter or above.
- Voice Library voices via the API return `paid_plan_required` on Free.
- `mp3_44100_192` needs Creator+; on Starter use `mp3_44100_128`.
- Use `eleven_multilingual_v2` for pt-BR, sending `say` as the request text.

Let a native speaker listen before choosing a voice; metrics do not replace
that.

## 4. Real people's voices

Do not synthesize or clone the voice of a real person who appears in the video
without them recording or authorizing it. First-person on-screen text with
their photo works; if they want narration, they record it and the same
pipeline applies.

## 5. API keys

Keys come from the environment, never from a repo file or the command line
(`ps` shows it). A secrets manager's `run` (bws, 1Password, sops) injects them
into the child process only. `bws run` joins arguments into one shell string:
re-quote a prompt with spaces (`printf '%q '`).

For sound effects, music, cleanup, transcription and dubbing, see the
`elevenlabs` skill.
