# Batch 2026-11-11-kinocut-2 — claims

**Notes, not run records.** Why media-agent 0.23.0 pins Kinocut 2.0.1 (was
1.16.4) and rewrites the Kinocut part of `video-editing`. 2.0.0 cut the MCP
server's default tool list; the skill named tools that are no longer on it.
The machine's owner approved the move. Nothing here compares an agent with and
without the skill.

**Machine.** Linux x86-64, ffmpeg 9.0.2 (static build) on PATH, uv 0.13.7.
`uvx --from kinocut==2.0.1` fetched a 1.5 MB wheel and 34 packages into uv's
cache. Test clip: 6 s, 640×360, 30 fps, H.264 and AAC, from ffmpeg's
`testsrc2` and a 440 Hz sine.

## Read upstream

- PyPI `kinocut` 2.0.1 (2026-11-10), the latest; README and `CHANGELOG.md` in
  `KyaniteLabs/kinocut`. 2.0.0's breaking change: the default MCP list is 18
  tools, and twelve left it, among them `search_tools`, `video_resize` and
  `video_convert`; each still works through its family or under
  `KINOCUT_TOOLS=all`. 2.0.0 also lists text overlays falling back to
  fontconfig's sans-serif and loudness checks working on FFmpeg 9.
- In the installed 2.0.1 package: `KINOCUT_TOOLS` accepts nothing (the
  default), `core`, `all` or `profile:<name>`, with tags such as `editor`
  (104 operations carry it), `hyperframes` (18) and `audio` (17); a profile
  adds its tools to the default list. A wrong value stops the server with a
  message naming the accepted forms. The HyperFrames lookup and
  telemetry rules are the same as in 1.16.4; a preview is refused unless
  HyperFrames is 0.8.104 or 0.8.140.

## Run here, through the MCP server

A stdlib client spoke JSON-RPC to `uvx --from kinocut==2.0.1 kino --mcp`
over stdio, one server per batch of calls.

- `tools/list`: 18 tools by default (`video_info`, `video_trim`,
  `video_merge`, `video_add_text`, `video_add_audio`, `video_doctor`,
  `video_extract_frame`, `video_shorts`, `list_operations`,
  `describe_operation` and eight `*_ops` families); 206 with
  `KINOCUT_TOOLS=all`, among them `search_tools` and `video_resize` and none
  of the families or the two lookup tools; 35 with `profile:audio`, the
  families kept. 1.16.4 listed 203. Start-up to the first answer:
  8.7 s with the package already cached.
- `list_operations {}`: 205 operations in 8 families (`video_edit_ops` 44,
  `video_effects_ops` 28, `audio_ops` 17, `video_ai_ops` 15, `image_ops` 8,
  `video_qc_ops` 15, `video_plan_ops` 51, `platform_ops` 27). With
  `query: "subtitle"` it returned three operations and their families.
- `describe_operation`: `video_resize` returned its schema, family
  `video_edit_ops` and CLI route `kino resize`; `resize` returned
  `unknown_operation`.

| Call | Result |
|---|---|
| `video_info` | `success`, numbers under `info`: 6.0 s, 640×360, 30 fps, h264/aac |
| `video_trim` `start 1, duration 2` | 2.000 s |
| the same again | `output_exists`, nothing written |
| `video_trim` without `output_path` | `src_trimmed.mp4` beside the input, 2.000 s |
| `video_trim` on a missing file | `invalid_input` |
| `video_merge` of two 2 s clips | 4.023 s |
| `video_edit_ops` / `video_resize` `aspect_ratio 9:16` | 1080×1920, picture letterboxed (frame viewed); 16 and 21 s here, while other jobs shared the machine |
| `video_edit_ops` / `video_crop` 360×360 | 360×360; again at 200×200 with `overwrite` inside `params`: replaced |
| `video_edit_ops` / `video_subtitles` with a one-cue `.srt` | caption in the frame at 1.8 s (viewed) |
| `video_edit_ops` / `video_normalize_audio` `target_lufs -16` | −21.8 LUFS before, −16.0 after (ffmpeg `ebur128`) |
| `video_extract_frame` `timestamp 1.5` | a PNG |
| `video_add_text` "Olá, título" | 6.0 s, the accented text drawn (frame viewed), on the ffmpeg build where a bare `drawtext` finds no font |
| `video_edit_ops` / `video_resize` onto an existing output | `output_exists`; with `overwrite: true` beside `operation`: replaced |
| `video_edit_ops` operation `video_resiz` | `isError`, `invalid_parameter`, a message that names neither the operation nor `describe_operation` |
| `video_edit_ops` / `video_resize` with an unknown argument | `invalid_parameter`, naming `describe_operation` |
| `platform_ops` / `hyperframes_doctor`, no HyperFrames CLI | `hyperframes_not_found` |
| `video_ai_ops` / `video_ai_transcribe` | `missing_whisper`, naming the `transcribe` extra |
| `video_doctor` | `success` |

**CLI, same package.** `kino --format json info`, `trim -s 0 -d 1.5 -o`,
`normalize-audio -l -16 -o` returned `success: true`; `kino doctor` exited 0
and found ffmpeg and ffprobe.

**Not run on 2.0.1.** The HyperFrames operations with a CLI present (they
worked on 1.16.4 in the 2026-11-11 HyperFrames batch), `video_add_audio`,
`video_shorts`, any profile other than `all`, and the server through a Claude
Code session: every MCP call above went through the stdlib client.

## Cold review

A subagent ran the pinned server on its own clip without this record's
conclusions. It confirmed the tool counts, every family call, the error codes,
`overwrite` in both places, the CLI fallback and the HyperFrames and Whisper
answers. Applied from its findings: the skill had said `KINOCUT_TOOLS=all` or a
profile lists every operation while keeping the families (`all` drops them, a
profile adds to the default), had sent a wrong operation name to
`describe_operation` (it needs the full name; `list_operations` finds it), and
had counted 16 tools in its opening line; the HyperFrames reference now states
the preview rule for every version. Its own resize runs took 3 to 10 s.
