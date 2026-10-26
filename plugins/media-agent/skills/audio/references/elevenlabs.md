# ElevenLabs

Checked against the docs on 2026-10-26.

## REST API or the canvas (MCP)

| | REST API (`scripts/eleven.py`) | ElevenCreative MCP (`creative_*`) |
|---|---|---|
| Local file as input | yes, the script uploads it | not on its own: upload opens a picker the user must use |
| Output | a file on disk | a signed URL that expires in 2 h; download at once |
| Offers | SFX, music, voice isolation, transcription, dubbing, TTS | all that, plus third-party image and video models, Topaz upscale, music from video, audio effects, brand kit, chained flows |

Input is a file on this machine: REST. Everything starts from a prompt, or the
user wants the canvas: MCP.

## Commands

From the skill's directory:

```bash
python3 scripts/eleven.py sfx "soft whoosh transition" -o whoosh.mp3 --seconds 1.5
python3 scripts/eleven.py music "calm corporate piano" -o bed.mp3 --seconds 40
python3 scripts/eleven.py isolate recording.wav -o clean.mp3
python3 scripts/eleven.py stt audio.wav -o words.json --lang por
python3 scripts/eleven.py credits
```

- SFX: `--seconds` 0.5–30, `--loop` for gapless ambience.
- Music: `--seconds` matches the cut (3–600 s), no loop or fade. Music from
  the video's own cuts exists only in the MCP (`video-to-music`); the API can
  also sign music with C2PA.
- Transcription: `stt` uses `scribe_v2` with word timestamps (`scribe_v1` is
  deprecated).
- Dubbing: `/v1/dubbing`, or MCP `dubbing-video`. Brand voice: Voice Design.

## Credits and license

- Check the balance with `eleven.py credits` before a batch; the counter lags
  a few minutes.
- The MCP's `estimate_only` costs nothing but creates an empty flow on the
  canvas each call: estimate once per task type, not per variation.
- Never repeat an MCP call to "try again": each call is a new, billed
  generation. Read the status of the one already running.
- The MCP generates 4 image variations by default (4x the cost).
- Commercial use starts at Starter. Self-serve plans exclude music for film,
  TV, radio and studio games ([music terms](https://elevenlabs.io/music-terms)).
- Not confirmed: the commercial terms for sound effects (sources cover music
  only). Dubbing and Voice Design have not been run with this skill.
