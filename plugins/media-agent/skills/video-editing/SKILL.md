---
name: video-editing
description: Edits finished video files with typed operations that return structured results, or re-renders the source when text or scenes change. Use to trim, cut a teaser, merge, resize, crop, burn captions, normalize an mp4's audio or extract a frame, or when Kinocut or ffmpeg is named.
---

# Editing finished video

## Which route

| Task | Route |
|---|---|
| Change text, scenes, order or format | re-render the source (`video-composition` skill): editing the source beats patching the mp4 |
| Cut, merge, resize, crop, extract a frame, burn in an `.srt` | a typed operation on the mp4 (Kinocut, below) |
| Normalize each voice-over sentence | before assembly (`voice` skill); it lands closer to -16 LUFS than normalizing the mixed file |
| A filter the typed tool lacks | raw ffmpeg |

Whatever the tool: check the output with `ffprobe` (duration, fps, streams)
and watch the cut points.

## Kinocut, the bundled tool

Kinocut wraps ffmpeg in typed operations: it validates the input first and
returns JSON with `success` and the output path, or a structured error with a
`suggested_action`, instead of pages of stderr. The plugin registers it as the
`kinocut` MCP server (pinned in the plugin's `.mcp.json`); its tools appear in
a new session. The same from the CLI, with the same pin, always with
`--format json` (otherwise the output is a human table):

```bash
uvx --from kinocut==1.16.4 kino --format json info video.mp4
uvx --from kinocut==1.16.4 kino --format json trim video.mp4 -s 0 -d 15 -o teaser.mp4
uvx --from kinocut==1.16.4 kino --format json normalize-audio video.mp4 -l -16 -o norm.mp4
uvx --from kinocut==1.16.4 kino doctor
```

- There are 190+ commands and some are shells: run a command once on a real
  file and check `success` and the output before building a flow on it.
- `video-ai-*`, `hyperframes-*` and several `sound-*` commands need optional
  extras (Whisper, Demucs, Real-ESRGAN, torch). Do not install them to get
  "all green": this plugin covers transcription, music and upscaling with
  other skills.
- It needs `uv`, `ffmpeg` and `ffprobe` on PATH. Without `uv` the MCP server
  does not start, and the error shows only in the MCP list.
