# media-agent

Media production by an agent on your own machine with an 8 GB GPU, where
commercial licensing matters and tools fail without saying so. One skill per
modality: its rules hold for any model of that kind, and each tool's notes sit
in the skill's `references/`, so a new model is a new reference file, not a
new skill.

```
/plugin install media-agent@4nrry
```

| Skill | Rules for | Bundled tools |
|---|---|---|
| `image-generation` | explore, choose on a contact sheet, final still, what never to generate | Grok Imagine (Grok Build, Hermes), Gemini (agy, API) wrappers; `contact-sheet.sh` |
| `video-generation` | still-to-video, one camera move, resolution by use, checking every clip | Gemini Omni and Grok video wrappers |
| `image-retouching` | weight licenses, removal vs inpainting, one GPU job at a time | headless ComfyUI (`comfy-run.py`) |
| `voice` | one sentence per file, caption vs spoken text, -16 LUFS, the durations JSON | `vo-normalize.sh`, `hermes-tts.sh` (xAI voice); TTS engine notes |
| `audio` | licenses and credits, exact-length music, SFX, fixing real recordings | ElevenLabs (`eleven.py`), ACE-Step, stock search (`media-search.py`) |
| `video-composition` | video as code: frame-driven scenes, captions from the voice JSON, formats from one source | Remotion, HTML + Chrome + ffmpeg |
| `video-editing` | re-render vs patch the mp4, checking the output | Kinocut, registered as an MCP server (`.mcp.json`) |
| `3d-turntable` | a 360° product turn as transparent frames | headless Blender (`turntable.py`) |

The hook `hooks/guard-vipsthumbnail.sh` (`PreToolUse` on `Bash(vipsthumbnail *)`)
warns when `-o name` without a slash will write next to the input file. It
never blocks.

The plugin does not decide licenses for you (Remotion's employee limit,
ElevenLabs' free tier): the skills state the rule and the user decides. Paths
and keys come from environment variables (`COMFY_HOME`, `*_API_KEY`).

**Evidence:** behavior checks from one real production, not effect
measurements —
[`bench/plugins/media-agent/results/2026-10-13-production-checks-CLAIMS.md`](../../bench/plugins/media-agent/results/2026-10-13-production-checks-CLAIMS.md).
