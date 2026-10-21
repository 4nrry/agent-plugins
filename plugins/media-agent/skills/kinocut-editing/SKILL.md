---
name: kinocut-editing
description: Edits already-rendered video with Kinocut — trim, merge, resize, crop, normalize audio, burn in captions, extract frames, check quality — through the MCP server this plugin registers or the `kino` CLI, with JSON responses and structured errors instead of ffmpeg stderr. Use when a task asks to cut a teaser or short version, trim, merge, concat, resize, crop, burn captions, normalize an mp4's audio, extract a frame or thumbnail, or "run the video through ffmpeg" after rendering, and when choosing between Kinocut, raw ffmpeg and re-rendering in Remotion.
---

# Editing finished video with Kinocut

Kinocut (Apache-2.0, local, no account) wraps ffmpeg in typed operations: it
validates input first and returns JSON with `success` and the output path. A
missing file returns
`{"success": false, "error": {"code": "invalid_input", "suggested_action": ...}}`
instead of pages of stderr.

The plugin registers the `kinocut` MCP server (via `uvx`, pinned in
`.mcp.json`); its tools appear in a new session. The same from the CLI, with the same pin as
`.mcp.json` — always with `--format json`, or the output is a human table:

```bash
uvx --from kinocut==1.15.1 kino --format json info video.mp4
uvx --from kinocut==1.15.1 kino --format json trim video.mp4 -s 0 -d 15 -o teaser.mp4
uvx --from kinocut==1.15.1 kino --format json normalize-audio video.mp4 -l -16 -o norm.mp4
uvx --from kinocut==1.15.1 kino doctor
```

## Which tool

| Task | Use | Why |
|---|---|---|
| Cut, merge, resize, crop, frame, burned-in `.srt` on a finished mp4 | Kinocut | validated operation, structured result |
| Change text, scenes, order or format | re-render (`video-remotion`) | editing the source beats patching the mp4 |
| Normalize each voice-over sentence before assembly | `vo-normalize.sh` (`voice-over`) | lands closer to -16 LUFS than Kinocut's `normalize-audio` |
| Normalize the final mp4 | Kinocut or `ffmpeg loudnorm` | half an LU is inaudible at the end |
| A filter Kinocut lacks | raw ffmpeg | what it calls underneath |

## What `doctor` does not tell you

- There are 190+ commands and some are shells: run a command once on a real
  file and check `success` and the output file before building a flow on it.
- `video-ai-*`, `hyperframes-*` and several `sound-*` commands need optional
  extras (Whisper, Demucs, Real-ESRGAN, torch, a Node package). Do not install
  them to get "all green": this plugin covers transcription, music and upscaling
  with other tools.
- It needs `uv`, `ffmpeg` and `ffprobe` on PATH. Without `uv` the MCP server
  does not start, and the error shows only in the MCP list.
- Untested: files with several audio tracks or variable frame rate.
