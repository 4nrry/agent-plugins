# Batch 2026-10-26-by-modality — claims

**Restructure notes, not run records.** media-agent 0.6.0 regroups its eight
skills by modality, with model-agnostic rules in each SKILL.md and each
tool's notes in `references/`. Old names map as: generative-media →
image-generation and video-generation, comfyui-retouching → image-retouching,
voice-over → voice, elevenlabs and music-and-stock → audio, video-remotion →
video-composition, kinocut-editing → video-editing, turntable-blender →
3d-turntable.

## Facts checked against official docs (a subagent, then spot checks)

| Fact | Result | Consequence |
|---|---|---|
| Veo 3.1 preview ids in the Gemini API | shut down 2026-10-22 (ai.google.dev/gemini-api/docs/video, read directly) | `veo.py` replaced by `omni.py` for `gemini-omni-1.1-flash` through the Interactions API; written from the docs; one live run, 360p from a still: 640x360, 24 fps, 10.0 s with AAC audio, 1.1 MB, 20 s wall, the still's palette kept |
| Kinocut latest | 1.16.4 | pin moved from 1.15.1; `info`, `trim` and the MCP `initialize` handshake ran on a test clip |
| ElevenLabs STT | `scribe_v1` deprecated | `eleven.py stt` sends `scribe_v2`; not run |
| RMBG-2.0 | own gated license, still non-commercial | table updated |
| FLUX.2 klein 4B | Apache-2.0 | listed as an alternative, not run |
| Pocket TTS Portuguese | `--language portuguese` | trap updated |
| YouTube Audio Library | music for videos you create; only Creator Music is YouTube-only | row corrected |
| Remotion | `<Video>` from `@remotion/media` now recommended; `layout="none"` throws from 5.0 | notes updated |
| Instagram "AI info" | from C2PA and IPTC metadata | provenance wording corrected |

Descriptions: 4,411 characters before, about 2,300 after. Lint
(`lint_extensions.py`) and `claude plugin validate --strict` pass.

## xAI on the SuperGrok subscription (live, n=1 each)

| Route | Result |
|---|---|
| TTS through Hermes (`xai`, voice `liora`, pt-BR), `hermes-tts.sh` | ok in 7 s: mp3, 24 kHz mono, 128 kb/s, 2.9 s, -20.1 LUFS |
| STT (`grok-voice-transcribe-2.0`) | no headless route: `hermes chat -t stt` returns `invalid_params`; transcription lives in Hermes's gateway only; Grok Build and Cursor CLI have no audio tools |
| Image through Hermes (`grok-imagine-image-2.0`), `hermes-image.sh` | ok in 17–21 s: JPEG 1280x720 at "1k"; a public x.ai CDN URL for 48 h |
| Video at 1080p, Grok Build `reference_to_video` | the agent asked for 1080p, then fell back to 720p: 1280x720, 24 fps, 6 s, with audio, 170 s |
| Video at 1080p, Grok Build `image_to_video` | refused: "resolution_name must be one of: 480p, 720p. Got 1080p." |
| Video through Hermes | its xAI plugin allows only 480p and 720p |
