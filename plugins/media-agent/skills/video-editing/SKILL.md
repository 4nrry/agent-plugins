---
name: video-editing
description: Edits a finished video file when only the rendered mp4 exists, with typed operations that return structured results; text or scene changes go back to the source. Use to trim, cut a teaser, merge, resize or crop an existing file, burn in an .srt or subtitles, normalize a finished mp4's audio or extract a frame, to break a video down frame by frame (cuts, flashes against their sound, when each word lands), to check a render before anyone watches it (flash safety, blank frames, platform limits, caption reading time, burned-in captions out of sync, missing glyphs), to cut dead air and retakes out of a recording by its word times without clipping a word, or when Kinocut or ffmpeg is named.
---

# Editing finished video

## Which route

| Task | Route |
|---|---|
| Change text, scenes, order or format | re-render the source (`video-composition` skill): editing the source beats patching the mp4 |
| Change only the sound (an effect, the music, levels) | remix the stems and mux onto the existing picture, `-map 0:v -map 1:a -c:v copy -c:a aac -ar 48000`, padded or cut with `-af apad -t <picture duration>`, not `-shortest`, which cuts the picture to a shorter mix (`video-composition` skill, "Build in layers"); no picture re-render, no picture re-encode (the audio is encoded to AAC) |
| Cut, merge, resize, crop, extract a frame, burn in an `.srt` | a typed operation on the mp4 (Kinocut, below) |
| Normalize each voice-over sentence | before assembly (`voice` skill); it lands closer to -16 LUFS than normalizing the mixed file |
| An operation Kinocut lacks (table below) | a pinned `ffmpeg-skill` script |
| A filter neither has | raw ffmpeg |
| Learn from a reference video, or check a render's timing | `scripts/breakdown.py` (below) |
| Check a render before anyone watches it | `scripts/render_qc.py` (below) |
| Cut dead air and retakes out of a recording, by its word times | `scripts/qa_cut.py` (below) |

Whatever the tool: check the output with `ffprobe` (duration, fps, streams)
and watch the cut points.

With raw ffmpeg, give `drawtext` a font file
(`drawtext=fontfile=/path/to/font.ttf:text=...`). Some builds find no font
by name and stop with `impossible to find font information`, with or without
`font=`. Subtitles burned through libass still
find fonts by name.

## Checking a render before anyone watches it

`scripts/render_qc.py all VIDEO --platform reels --captions VOICE.json --font FONT`
runs every mechanical check, exits 1 when one fails and 2 when a check could not run. Each check also runs
alone (`flash`, `blank`, `frames`, `banding`, `delivery`, `reading`,
`captions`, `fonts`); `rhythm` runs only on its own; `--json` gives machine output. It needs ffmpeg, ffprobe
and numpy; `captions` also needs tesseract.

| Check | Fails when | Source |
|---|---|---|
| `flash` | more than 3 general or red flashes in any second over a quarter of any ⅓×⅓ field | WCAG 2.2 SC 2.3.1; counter after vargHQ `media-judge` |
| `blank` | the frame is one flat colour for 1 s or more, fades at the ends aside | after Content-Agent-Kit `blank-check.mjs` |
| `frames` | black frames of 0.25 s or less cut into the picture; a one-frame glitch only warns | after vargHQ `media-judge` |
| `banding` | warns at CAMBI 5 in dark frames, 7.5 in bright ones; skipped without an ffmpeg built with libvmaf | Netflix CAMBI; split after vargHQ |
| `delivery` | a platform's official hard limit is broken (length and size everywhere; container on Reels; codec, frame rate and resolution on TikTok; shape on Shorts); recommendations, unconfirmed numbers and a silent track only warn | each platform's own pages, cited in the code |
| `reading` | a caption leaves the screen sooner than characters ÷ 15 + 1.5 s | after lemo-opuscar `readcheck.mjs` |
| `captions` | no caption is read on screen; under 65% of the file's captions, or of their time under 55%, are matched by OCR; or starts sit a median of 350 ms or a p95 of 900 ms from the file's times | 45ck/content-machine `caption-sync.ts` |
| `fonts` | the font has no glyph for a character in the text, such as an accent | reads the font file, no network |
| `rhythm` | only warns, and only when asked (not in `all`): shot lengths vary by a coefficient of variation under 0.25 (every shot the same length reads as slides), or under 25% of frames are still, or no still stretch reaches 1 s (motion that never rests) | thresholds from feitangyuan/onetake `verify_promo.py`, no code |

- The captions file can be the voice JSON, a `{text, start, end}` list or
  WhisperX segments; a word-by-word list is skipped.
- Instagram publishes no organic Reels spec: its numbers come from Meta's
  Reels ads guide, and its pages give both 3 and 20 minutes as the limit.
- `captions` samples 3 frames a second in the bottom 35% of the frame (or
  `--band TOP:HEIGHT`), retries in a centre band when too few captions match
  or the OCR confidence is low (not on drift alone), and moves
  each start to the frame where the band changed, so drift is measured to the
  frame. It reads light text only, not dark text on a light box. Without
  tesseract it is skipped. `--ocr-lang auto` reads with `por` when the
  captions have Portuguese accents and that language is installed, else
  `eng`; the summary says which ran.
- `rhythm` is for motion made as code (HyperFrames, Remotion, a Three.js
  stage); live footage rarely rests, and that is not a defect. Shots are the
  hard cuts it finds; a one-take piece has none, so pass its beat times with
  `--shots 2.5,4,9.2`. Cadence needs 3 shots or more, else it is skipped. A
  still frame is one under 0.5 of 255 mean difference from the frame before,
  black frames aside. A cut is a one-frame jump: fades, flashes under 0.2 s
  and a cut inside fast motion all go unseen, so for a busy piece pass
  `--shots`.
- The ⅓-frame field is WCAG's desktop approximation; on a phone the check is
  stricter than needed. A flash failure is a frame range to look at, not a
  verdict: two real renders failed on bursts that a person should judge.
- Licences of the adapted code (here and in `qa_cut.py`) are in
  `scripts/THIRD_PARTY_NOTICES.md`.

## Cutting a recording by its words

`scripts/qa_cut.py` (after vargHQ `edit-footage-with-code`, MIT) cuts the dead
air and the retakes out of a talking-head or voice recording, renders the cut
and checks that no word was cut. It needs ffmpeg and ffprobe, nothing else:
the word times come from the `audio` skill (WhisperX or Scribe JSON, or a
`{word, start, end}` list).

```bash
python3 scripts/qa_cut.py plan take.mp4 --words words.json --out edit   # edl.json, intended.json, review.md
python3 scripts/qa_cut.py render edit/edl.json [--fcpxml]                # edit/cut.mp4, then its checks
python3 scripts/qa_cut.py qa edit/cut.mp4 --edl edit/edl.json --heard heard.json
```

- Show `review.md` to the person and render only after a yes. Change only
  `in` and `out` in `edl.json`; `render` recomputes the rest.
- Pauses come from the take's own audio, not from gaps between words: an ASR
  stretches words across pauses. A pause is held at 0.22 s, or 0.36 s after a
  sentence, and only when that removes 0.2 s or more: so only pauses of
  0.42 s or more are cut, or 0.56 s after a sentence. A retake is cut only
  when the repeat covers most of the attempt; stutters are listed, never cut;
  fillers only with `--cut-fillers`.
- A quiet word the take's level calls silence still counts when its own
  audio is over -50 dBFS. A word with no sound at its times, or past the end
  of the media, is listed in `review.md` and left out of the check.
- `render` refuses a variable-frame-rate take: conform it first
  (`ffmpeg -i take.mov -vf fps=30,format=yuv420p -fps_mode cfr -c:a copy take.mp4`),
  then plan again.
- `qa` fails on a join that cuts through sound, a kept word the edit list
  clips (sound over -50 dBFS at the edge) or leaves out, a pause over 0.6 s, an opening on silence, black or
  flash frames, and loudness off -16 LUFS (`--lufs -14` for vargHQ's
  target). `render` reports loudness without judging it: a rough cut is mixed
  later. With `--heard`, a fresh transcript of the cut, under 95% of the
  intended words heard or a phrase said twice fails.
- A join with no silence to cut in stays flagged until a person has heard it:
  then pass `--accept-join SECONDS`.
- Look at `joins.jpg` and `contact.jpg`, and listen to every join: a pass
  means nothing measurable is broken, not that the cut is good.
- `--fcpxml` writes `cut.fcpxml` for a hand trim in Resolve or Final Cut when
  joins keep sounding wrong; each clip keeps its handles. It is checked as
  XML here, not yet opened in either editor.

## Breaking a video down frame by frame

To label how each shot of a reference was made (filmed, AI, 3D, code) and
route a remake, see [references/production-types.md](references/production-types.md).

`scripts/breakdown.py VIDEO --out DIR [--words WORDS.json]` reads a finished
mp4 and writes `report.md` and `report.json`. It needs ffmpeg, numpy and
Pillow. The report has:

- the hard cuts;
- the shots between cuts: duration, layout (`split` when a horizontal divider
  separates top B-roll from bottom speaker, else `full`), motion activity
  (`active` vs `static_hold`), frozen head/tail frame count, and whether the
  entry cut is a jump cut (high frame difference while global scene structure
  stays near the previous shot);
- stalled per-tile motion: flags any tile of the 3×4 grid that moved for
  `>= 2 s` and then froze for `>= 1.5 s` while another region kept moving
  (catches I2V clips or PiPs whose motion ran out mid-shot);
- short-form opening audit (`0–2 s` on vertical/square videos `<= 180 s`):
  checks motion in the first `2 s`, first shot length (`<= 5 s`), first sound
  above `-40 dBFS` (`<= 1 s`), and whether the opening `2 s` sits `>= 10 dB`
  under median volume;
- the change zones, each with a sheet of its consecutive frames;
- the flashes, each with its nearest low hit in frames;
- the sound onsets, loudness and silences;
- with `--words` (WhisperX JSON or a list of `{word, start}`), each word's
  frame.

It also writes contact sheets every half second. Use it on a reference
before copying what it does, and on a render before delivery.

- A cut needs a frame that changes far more than its neighbours and does not
  come back. A flash rises and falls with the same picture before and after,
  and its fall is part of it. So a whip, a fade to a white card, a camera
  move or a held white frame reads as a zone, not a cut.
- Its thresholds were tuned on four clips and tried on no other: a 25 s ad
  (0 cuts and 4 flashes, as read by eye), two synthetic clips (a cut, a
  flash, a held flash) and a 6 s Three.js render (3 flashes, 0 cuts). The
  record is the Three.js stage one linked from the plugin's README.
- A sound can read one frame early: AAC spreads a hit's energy a little
  before it.
- Text appearing on screen is a small change under the zone threshold: read
  it off the sheets against the word table.

## Checking SFX sync against visual motion

`scripts/sync_check.py` (adapted from MIT `4nrry/claude-code-video-toolkit`)
aligns each sound effect's loudest `50 ms` peak with the corresponding visual
event (`peak`, `impact`, or `onset` inside an ffmpeg crop region `w:h:x:y`).
Use it before rendering to find the exact placement on a generated clip, or
after rendering as a `±0.1 s` gate (exits `1` if off):

```bash
python3 scripts/sync_check.py --clip shot.mp4 --sfx hit.wav --window 1.5:3.5 --kind impact
python3 scripts/sync_check.py --video final.mp4 --sfx hit.wav --at 4.20 --region 540:540:270:600
python3 scripts/sync_check.py --video final.mp4 --cues cues.json --tolerance 0.1 --json
```

## What Kinocut lacks

Kinocut 2.0.1 has no operation for these; `4nrry/ffmpeg-skill` (fork of
`kajisho5/ffmpeg-skill`, MIT, stdlib Python) does, compared against Kinocut
2.0.1's source. The scripts were read, not yet run here.

| Need | Script |
|---|---|
| Different speed per segment (a ramp) | `scripts/speedramp.py` (Kinocut's `video_speed` takes one factor) |
| Line up two cameras or a separate audio take by cross-correlation, fix drift | `scripts/sync.py`; `scripts/multicam.py` to cut between them |
| HDR to SDR tone mapping | `scripts/color.py` |
| Find and crop black borders; straighten a tilted horizon | `scripts/cropdetect.py`, `scripts/straighten.py` |
| Freeze a frame; loop or boomerang the picture | `scripts/freeze.py`, `scripts/loop.py` |
| Frame-exact cut that re-encodes only the partial GOPs | `scripts/cut.py --smart` |

Clone it pinned, run the script directly, and leave the rest alone:

```bash
git clone --depth 1 --branch v4.7.0 https://github.com/4nrry/ffmpeg-skill.git
python3 ffmpeg-skill/scripts/speedramp.py --help
```

The scripts import `scripts/_common/`, so copy that folder with any script
you move. Never run `npx ffmpeg-skill setup`: it may run
`sudo apt-get install` and installs itself into every agent's skills folder.
The repo's `.claude/settings.json` turns on six outside plugins; do not open
an agent session inside the clone.

## Kinocut, the bundled tool

Kinocut wraps ffmpeg in typed operations: it validates the input first and
returns JSON with `success` and `output_path`, or `success: false` with an
`error.code` and a message that says how to retry, instead of pages of stderr.
The plugin registers it as the `kinocut` MCP server (pinned in `.mcp.json`).
By default the server lists 18 tools: eight called by name, eight families
that run any other operation by name, and `list_operations` and
`describe_operation` to find one. Always pass absolute paths.

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

Nothing runs on a wrong call, and the error says little. A short name
(`resize`) or a misspelt one returns `invalid_parameter` without naming the
operation: look the name up with `list_operations` and its `query`. An
argument the operation does not take returns `invalid_parameter` naming the
operation: read its schema with `describe_operation` and call again.

`KINOCUT_TOOLS`, set where the server starts, changes the list: `all` lists
every operation as a tool of its own and drops the families and the two
lookup tools (`search_tools` takes their place); `profile:<name>` adds one
job's tools to the default 18. Leave it unset: this table assumes the default.

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
