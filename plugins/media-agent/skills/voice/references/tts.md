# TTS engines

Checked against the vendors' docs and model cards on 2026-10-26. Check the
license and the plan's terms again before a commercial piece.

A subscription route spends the plan's quota and nothing more; an API-key
route bills every call to that key. Prefer the subscription routes when the
key's budget belongs to something else.

| Engine | Billed to | Runs on | License | Trap |
|---|---|---|---|---|
| ElevenLabs | ElevenLabs plan credits | cloud | paid plan for commercial use | best pt-BR by a margin among the paid APIs |
| xAI TTS, voice `liora`, through Hermes | Grok subscription | cloud | xAI's terms | `scripts/hermes-tts.sh "text" s1.mp3`; mp3 24 kHz mono at about -20 LUFS, so normalize it like the rest |
| Pocket TTS (Kyutai) | nothing (local) | CPU, `uv tool install pocket-tts` | code MIT, weights CC-BY-4.0 (credit) | without `--language portuguese` Portuguese comes out as accented English; larger `_24l` variants exist |
| Kokoro-82M | nothing (local) | CPU | Apache-2.0 | pins Python below 3.13: `uv venv -p 3.12` |
| Qwen3-TTS 1.7B | nothing (local) | 8 GB GPU | Apache-2.0 | Portuguese sounds European; `--instruct` does not fix it |
| Chatterbox Multilingual | nothing (local) | 8 GB GPU, Python 3.11 | MIT | the `perth` watermarker is `None` in some builds: fall back to the dummy one |
| Gemini TTS (`gemini-3.8-flash-tts`) | Gemini API key, per use | cloud, Gemini API | Gemini API terms | not tried yet |

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
