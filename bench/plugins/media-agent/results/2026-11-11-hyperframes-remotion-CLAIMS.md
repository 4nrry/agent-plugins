# Batch 2026-11-11-hyperframes-remotion — claims

**Notes, not run records.** Why media-agent 0.20.0 adds a HyperFrames
reference to `video-composition` and corrects the Remotion one. Before it the
skill knew two compositors, Remotion (checked at 4.0.538) and an HTML capture
written by hand; HyperFrames was one row in a table of tools, and
`video-editing` said Kinocut's `hyperframes_*` tools needed optional Python
extras.

**Read, not run.** The HyperFrames repository at tag v0.9.35 and the Remotion
repository at tag v4.0.543, both on 2026-11-11: README, LICENSE, the docs
directories, the published skills, npm metadata and `gh api` for stars and
release dates. License terms, prices, the telemetry rules, the contract and
the planned 5.0 changes in the two references come from there.

**Machine.** Linux x86-64, 22 threads, 30 GB RAM, Node 26.5.1, ffmpeg 8.1.2,
Google Chrome 157. Neither tool was installed before.

**One composition, both tools.** A 3 s, 1280×720, 30 fps title that fades in,
slides and scales. One run each unless a count is given.

| | HyperFrames 0.9.35 | Remotion 4.0.543 |
|---|---|---|
| Run as | `npx --yes hyperframes@0.9.35` | a project with `remotion`, `@remotion/cli`, `@remotion/transitions`, `react`, `react-dom` |
| On disk before a render | 110 MB in the npx cache | 252 MB of `node_modules` (244 packages, 8 s to install) |
| First render also downloaded | `chrome-headless-shell` 152.0.7977.30, 261 MB, into `~/.cache/hyperframes/chrome` | Chrome Headless Shell 158.0.8127.2, 102.5 MB (243 MB on disk), into `node_modules/.remotion` |
| Render time | 4.6 s (draft), 4.0 s and 3.3 s (default), as the CLI printed | 15.9 s wall with the download, 4.8 s wall after |
| Output | H.264 High, yuv420p, 90 frames, 157 KB; `--quality draft` gave Constrained Baseline | H.264 High, yuv420p, 90 frames, 51 KB, no audio stream |
| Two renders in a row | same sha256 | same sha256 |

**HyperFrames, seen in those runs.**

- `doctor --json` exited 0 with `ok: false`; the failing checks were
  whisper-cpp, Kokoro and MusicGen. It reported "Chrome: system:
  /usr/bin/google-chrome", and the render downloaded its own headless shell
  anyway.
- `lint` gave 0 errors and one warning; `check --json` took 2.3 s and sampled
  9 times for layout and 5 for contrast.
- `snapshot --at 0.5,2.5` wrote three PNGs and a contact sheet.
- After `check`, a `warmCheck.js 300000` process stayed with a headless Chrome
  as its child, about 310 MB resident in those two processes, four and a half
  minutes later.
  It was stopped by PID.
- It wrote `~/.hyperframes/config.json` and, under `~/.cache/hyperframes/`,
  `fonts/inter/` (eleven files from Google Fonts for a `sans-serif` title) and
  `history/`.
- `telemetry status` showed "disabled" with `HYPERFRAMES_NO_TELEMETRY=1`, and
  "disabled, source: config" after `telemetry disable` without the variable.
- `browser clear` removed the 261 MB download.

**Kinocut 1.16.4 with HyperFrames 0.9.35**, through the MCP server.
`hyperframes_doctor` with no CLI installed returned `success: false`, code
`hyperframes_not_found`. The lookup order in the reference was read in
`hyperframes_engine.py`. After `npm install --save-dev hyperframes@0.9.35` in
the project (109 MB), `hyperframes_info`, `hyperframes_validate`,
`hyperframes_inspect` and `hyperframes_render` returned `success: true`; the
inspect result carried `_meta.deprecated: true`, and the render wrote an mp4
in 4.5 s.

**Remotion, three claims of the old reference re-run on 4.0.543**, one still
each.

- A `TransitionSeries` whose children were `React.Fragment`s rendered with no
  error, and a frame in the middle of the fade was the blend of the two
  scenes. The package has a `flatten-children.js`. The old text said Fragment
  children were rejected; the version that changed it was not found.
- `<Sequence from={T} layout="none">` inside a `TransitionSeries.Sequence`
  rendered. The 5.0 migration page removes `layout="none"` from
  `<TransitionSeries>`, not from `<Sequence>`, which the old text had mixed up.
- `<Track name="Scenes">` with two `<Sequence>` children rendered.

**Carried over, not re-measured.** In the Remotion reference: the legacy
`<Video>` dropping frames, `dangerouslySetInnerHTML`, `Config.setRspack`, the
Tailwind alias, and `--gl=swangle` rendering empty frames with
`@remotion/three`.

**Not measured.** Audio in either tool: no voice, music or loudness went
through a render, so what the HyperFrames mix does to levels is unknown.
Sub-compositions, the registry (`catalog`, `add`), `preview`, `--docker`, alpha
formats, and one source in several aspect ratios in HyperFrames.
`HYPERFRAMES_BROWSER_PATH`. Remotion Studio and its visual edits, `@remotion/gsap`,
`@remotion/effects`, `open-timeline import`. Kinocut's other `hyperframes_*`
tools and all `revideo_*` tools. Neither vendor's skills or plugin were
installed, and no model was run on the changed skill text. Nothing was rendered
in any cloud and no account was signed in.
