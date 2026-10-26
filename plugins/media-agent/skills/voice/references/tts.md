# TTS engines

Checked against the vendors' docs and model cards on 2026-10-26. Check the
license and the plan's terms again before a commercial piece.

| Engine | Runs on | License | Trap |
|---|---|---|---|
| ElevenLabs | cloud | paid plan for commercial use | best pt-BR by a margin |
| Pocket TTS (Kyutai) | CPU, `uv tool install pocket-tts` | code MIT, weights CC-BY-4.0 (credit) | without `--language portuguese` Portuguese comes out as accented English; larger `_24l` variants exist |
| Kokoro-82M | CPU | Apache-2.0 | pins Python below 3.13: `uv venv -p 3.12` |
| Qwen3-TTS 1.7B | 8 GB GPU | Apache-2.0 | Portuguese sounds European; `--instruct` does not fix it |
| Chatterbox Multilingual | 8 GB GPU, Python 3.11 | MIT | the `perth` watermarker is `None` in some builds: fall back to the dummy one |
| Gemini TTS (`gemini-3.8-flash-tts`) | cloud, Gemini API | Gemini API terms | not tried yet |

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
