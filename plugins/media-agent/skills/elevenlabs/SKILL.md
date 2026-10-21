---
name: elevenlabs
description: Uses ElevenLabs beyond voice-over in a video piece — transition and UI sound effects, music of an exact length, cleaning up a real phone recording, word-timed transcription for captions, dubbing into another language, a brand voice, and the ElevenCreative canvas (MCP) for image, video, upscale and music from video. Says when to use the REST API and when the MCP, what each costs in plan credits, and what the Starter license covers. Use when a task asks for SFX, a whoosh or click sound, a soundtrack, custom music, audio cleanup, noise removal, voice isolation, transcription, captions for recorded video, dubbing, an English or Spanish version, a brand voice, voice design, or ElevenCreative.
---

# ElevenLabs beyond voice-over

Voice-over itself is in the `voice-over` skill.

## Which path

| | REST API (`scripts/eleven.py`) | ElevenCreative MCP (`creative_*`) |
|---|---|---|
| Local file as input | yes, the script uploads it | not on its own: upload opens a picker the user must use |
| Output | a file on disk | a signed URL that expires in 2 h; download at once |
| Offers | SFX, music, voice isolation, transcription, dubbing, TTS | all that plus third-party image and video models, Topaz upscale, music from video, audio effects, brand kit, chained flows |
| Fits | local pipeline steps, batches, no human | generation from text, chaining nodes, a user who will keep working on the canvas |

Input is a file on this machine: REST. Everything starts from a prompt or the
user wants the canvas: MCP.

## Credits

- Check the balance with `scripts/eleven.py credits` before a batch; the API
  counter lags a few minutes.
- The MCP's `estimate_only` costs nothing but creates an empty flow on the
  canvas each call: estimate once per task type, not per variation.
- Never repeat an MCP call to "try again": each call is a new, billed
  generation. Read the status of the one already running.
- The MCP generates 4 image variations by default (4x the cost).
- Video models cost a large share of a month's credits per clip; generate video
  through the `generative-media` skill instead.

## Uses worth the plan

From this skill's directory:

```bash
python3 scripts/eleven.py sfx "soft whoosh transition" -o whoosh.mp3 --seconds 1.5
python3 scripts/eleven.py music "calm corporate piano" -o bed.mp3 --seconds 40
python3 scripts/eleven.py isolate recording.wav -o clean.mp3
python3 scripts/eleven.py stt audio.wav -o words.json --lang por
python3 scripts/eleven.py credits
```

- **SFX:** short, concrete prompts ("soft click pop for UI element
  appearing"); `--seconds` 0.5–30, `--loop` for gapless ambience. Normalize
  with the music.
- **Music of an exact length:** `--seconds` matches the cut, no loop or fade.
  Commercial use starts at Starter; self-serve plans exclude film, TV and
  games ([pricing](https://elevenlabs.io/pricing)). Music from the video's own
  cuts exists only in the MCP (`video-to-music`).
- **Clean a real recording:** `isolate` on a phone recording with street or fan
  noise.
- **Captions for real audio:** `stt` returns word timings. It normalizes
  numbers and currency and can drop a leading conjunction; review before
  burning in. For generated voice-over, captions come from the voice-over JSON.
- **Another language:** for institutional pieces, translate the voice-over JSON
  and generate TTS in that language (captions stay exact). Use dubbing
  (`/v1/dubbing`, MCP `dubbing-video`) for real speech that cannot be
  re-recorded.
- **Brand voice:** Voice Design creates an account-owned voice from a
  description. Never imitate a real person.

## Worth it on the canvas

- **Brand kit from the website** (`creative_create_brand_kit_from_website`):
  once per brand.
- **Topaz upscale** of images and video, e.g. a low-resolution Grok clip.
  Estimate first.
- **Audio effects** (phone, radio, room, distance): free and fast; always the
  last step.

## Unverified

- The commercial license terms for sound effects (sources cover music only).
- Dubbing and Voice Design have not been run with this skill.
