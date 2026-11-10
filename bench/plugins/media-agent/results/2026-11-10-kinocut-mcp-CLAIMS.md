# Batch 2026-11-10-kinocut-mcp — claims

**Notes, not run records.** Why media-agent 0.19.0 teaches Kinocut's MCP tools
in `video-editing` and moves stock libraries to their own skill. The 0.2.0
audit found that the plugin registers Kinocut as an MCP server (203 tools
listed in that session) while the skill taught four CLI commands and named no
tool, and that a skill named `audio` owned stock footage and photos.

**Kinocut tools, run once each.** 2026-11-10, kinocut 1.16.4 as pinned in
`.mcp.json`, called through the MCP server from a Claude Code session, on a
6 s 640×360 30 fps H.264/AAC clip made with ffmpeg's `testsrc2` and a sine
tone. Outputs read with ffprobe.

| Tool | Call | Result |
|---|---|---|
| `video_info` | the clip | duration 6, 640×360, 30 fps, h264/aac |
| `video_trim` | `start: 1`, `duration: 2` | 2.000 s |
| `video_trim` | same `output_path` again | `success: false`, code `output_exists` |
| `video_trim` | no `output_path` | `src_trimmed.mp4` beside the input |
| `video_trim` | a path that does not exist | `success: false`, code `invalid_input`, a `suggested_action` |
| `video_merge` | two 2 s clips | 4.023 s |
| `video_merge` | a 640×360 clip, then a 360×360 one | 640×360, 10.08 s |
| `video_resize` | `aspect_ratio: "9:16"` | 1080×1920, the picture letterboxed (one frame viewed) |
| `video_crop` | `width: 360`, `height: 360` | 360×360 |
| `video_subtitles` | a one-cue `.srt` | the text is in the frame at 1.5 s (viewed) |
| `video_normalize_audio` | `target_lufs: -16` | -21.8 LUFS before, -16.0 after (ffmpeg `ebur128`) |
| `video_extract_frame` | `timestamp: 1.5` | a PNG |
| `search_tools` | `"subtitle"` | 4 tools with their required parameters |

**From the cold review, one run each on its own clips.** With `start: 1.5` on
a clip whose only keyframe is at 0, `video_trim` gave the same file (same
sha256) with and without `accurate: true`, starting at source frame 45: the
default was already frame-exact there, so the skill only says when to ask for
`accurate`. A `.vtt` burned in. `video_crop` without `x` and `y` was centered.
Crop, resize and extract_frame also wrote beside the input. `video_merge`
refused an existing output too, and `overwrite: true` replaced one on trim.

**Carried over, not re-measured.** That some tools are shells and that the
`video_ai_*`, `hyperframes_*` and `sound_*` tools need optional extras comes
from the 0.18.3 skill, written about the CLI commands of the same names.

**page-check.** One CI job on 2026-11-10 failed with "Chrome did not open its
DevTools port in 20 s" and nothing on stderr; the other job of the same commit
passed. `launch()` now tries once more on that error only, after printing the
first attempt's message. The reviewer ran it against a binary that never opens
the port: two attempts, 40 s, exit 2, no process or temp directory left. A
slow start on the one launch the self-test times would still fail its "the
redirect does not hold the run up" check.

**Not measured.** A clip where the default trim lands off the requested
frame. `.ass` subtitles. The CLI commands left in the skill as the
fallback were not re-run. No `video_ai_*`, `hyperframes_*` or `sound_*` tool
was called. Which of `audio` and `stock-media` a model loads for a stock or
music request: no model was run on the new descriptions. The retry in
page-check: the slow start was not reproduced, so only the self-test covers
the file.
