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
| Veo 3.1 preview ids in the Gemini API | shut down 2026-10-22 (ai.google.dev/gemini-api/docs/video, read directly) | `veo.py` replaced by `omni.py` for `gemini-omni-1.1-flash` through the Interactions API; written from the docs, checked offline (arguments, response parsing), **not run against the API** |
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
