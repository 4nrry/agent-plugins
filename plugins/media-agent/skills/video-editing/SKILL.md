---
name: video-editing
description: Edits a finished video file when only the rendered mp4 exists, with typed operations that return structured results; text or scene changes go back to the source. Use to trim, cut a teaser, merge, resize or crop an existing file, burn in an .srt or subtitles, normalize a finished mp4's audio or extract a frame, or when Kinocut or ffmpeg is named.
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

With raw ffmpeg, give `drawtext` a font file
(`drawtext=fontfile=/path/to/font.ttf:text=...`). Some builds find no font
by name and stop with `impossible to find font information`, with or without
`font=`. Subtitles burned through libass still
find fonts by name.

## Kinocut, the bundled tool

Kinocut wraps ffmpeg in typed operations: it validates the input first and
returns JSON with `success` and `output_path`, or `success: false` with an
`error.code` and a message that says how to retry, instead of pages of stderr.
The plugin registers it as the `kinocut` MCP server (pinned in `.mcp.json`).
The server lists eight tools by name and reaches every other operation
through eight family tools; always pass absolute paths.

| Task | Call | Note |
|---|---|---|
| Duration, size, fps, codecs | `video_info` | before any edit; the numbers are under `info` |
| Cut a segment | `video_trim` | `start` plus `duration` or `end`; add `accurate: true` when the cut must be frame-exact |
| Join clips | `video_merge` | `clips` in order; the output takes the first clip's size |
| Burn in a title | `video_add_text` | finds its own font; a wording change on a video built from source goes back to the source |
| One frame | `video_extract_frame` | `timestamp` in seconds |
| Change size or ratio | `video_edit_ops`, operation `video_resize` | `aspect_ratio` pads with black bars, it does not crop: to fill the frame, `video_crop` first |
| Crop | `video_edit_ops`, operation `video_crop` | `width` and `height`, centered unless `x` and `y` are given |
| Burn in subtitles | `video_edit_ops`, operation `video_subtitles` | `subtitle_path` to an `.srt`, `.vtt` or `.ass` |
| Loudness of a finished file | `video_edit_ops`, operation `video_normalize_audio` | `target_lufs: -16` |
| Anything else | `list_operations`, then `describe_operation` | `list_operations` takes a `query` or a `family` and gives each operation's required parameters; `describe_operation` gives one operation's full schema and its family |

A family call names the operation in full and nests its arguments:

```json
{"operation": "video_resize", "params": {"input_path": "/abs/in.mp4", "aspect_ratio": "9:16"}}
```

A short name (`resize`), a misspelt one or an argument the operation does not
take returns `success: false` with `invalid_parameter` or `unknown_operation`
and nothing runs: fetch the schema with `describe_operation` and call again.
Setting `KINOCUT_TOOLS=all` (or `profile:<name>`) where the server starts lists
every operation as a tool of its own; the families run the same code.

- Without `output_path` the result goes beside the input (`clip_trimmed.mp4`).
  An existing output is refused with `output_exists` unless `overwrite: true`,
  which a family call takes beside `operation` or inside `params`.
- Some of the 200-odd operations are shells. `describe_operation` describes a
  contract, not what is installed: run an operation once on a real file and
  check `success` and the output before building a flow on it.
- `video_ai_ops` and several `audio_ops` operations need optional extras
  (Whisper, Demucs, Real-ESRGAN, torch) and return a code such as
  `missing_whisper` without them. Do not install them to get "all green":
  this plugin covers transcription, music and upscaling with other skills.
- The `hyperframes_*` operations, in `platform_ops`, build a video from its
  source, which is the `video-composition` skill's work. They need the
  HyperFrames CLI where Kinocut can find it and return `hyperframes_not_found`
  without it. In a HyperFrames project that lacks it, add it as that skill's
  HyperFrames reference says (exact version, size told to the user first).
  Outside such a project there is nothing for them to render: do not install
  it to clear the error.
- The server needs `uv`, `ffmpeg` and `ffprobe` on PATH. Without `uv` it does
  not start, and the error shows only in the MCP list.

Where the tools are missing (the server did not start, or a harness that does
not load `.mcp.json`), the same operations exist in the CLI, with the version
pinned in `.mcp.json` and always with `--format json` (otherwise the output is
a human table):

```bash
kino="uvx --from kinocut==<version from .mcp.json> kino"
$kino --format json info video.mp4
$kino --format json trim video.mp4 -s 0 -d 15 -o teaser.mp4
$kino --format json normalize-audio video.mp4 -l -16 -o norm.mp4
$kino doctor
```
