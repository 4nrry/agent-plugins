# media-agent

Media production by an agent on your own machine with an 8 GB GPU, where
commercial licensing matters and tools fail without saying so: voice-over,
music and stock media, retouching, generated images and video, a 3D product
turntable, and the film rendered as code.

```
/plugin install media-agent@4nrry
```

| Skill | Does |
|---|---|
| `voice-over` | Local TTS or ElevenLabs, one sentence per file, -16 LUFS, a durations JSON that drives captions and ducking (`vo-normalize.sh`) |
| `elevenlabs` | SFX, exact-length music, cleanup, word-timed transcription, dubbing, brand voice; REST vs MCP; credits (`eleven.py`) |
| `music-and-stock` | ACE-Step 1.5 within 8 GB; Openverse, Freesound, Pexels, Pixabay with per-item licenses (`media-search.py`) |
| `comfyui-retouching` | Headless ComfyUI with commercially licensed models: background, upscale, logo removal, inpaint, stills (`comfy-run.py`) |
| `generative-media` | Which generator for which task, the still-to-video flow, prompts, what never to generate (grok, agy, Veo, Nano Banana wrappers) |
| `turntable-blender` | 360° turntable of a `.glb` in headless Cycles, transparent PNGs (`turntable.py`) |
| `video-remotion` | Video as code in Remotion or HTML + Chrome + ffmpeg, four formats and a carousel from one source |
| `kinocut-editing` | Editing finished video through the Kinocut MCP server this plugin registers (`.mcp.json`) |

The hook `hooks/guard-vipsthumbnail.sh` (`PreToolUse` on `Bash(vipsthumbnail *)`)
warns when `-o name` without a slash will write next to the input file. It
never blocks.

The plugin does not decide licenses for you (Remotion's employee limit,
ElevenLabs' free tier): the skills state the rule and the user decides. Paths
and keys come from environment variables (`COMFY_HOME`, `*_API_KEY`).

**Evidence:** behavior checks from one real production, not effect
measurements —
[`bench/plugins/media-agent/results/2026-10-13-production-checks-CLAIMS.md`](../../bench/plugins/media-agent/results/2026-10-13-production-checks-CLAIMS.md).
