# HyperFrames

Checked against the repository at tag v0.9.35 on 2026-11-11. What was run is
in the
[2026-11-11 record](https://github.com/4nrry/agent-plugins/blob/main/bench/plugins/media-agent/results/2026-11-11-hyperframes-remotion-CLAIMS.md).

HTML, CSS and a paused animation timeline rendered to video: the renderer
seeks every frame in headless Chrome and ffmpeg encodes and mixes the audio.
HeyGen maintains it and releases several times a day (eight versions in the two
days before this check), so pin one version in every command: 0.9.35, the one
these notes were checked on, unless the project already pins another.

## Contents
- License and what leaves the machine
- Setup
- The contract
- Loop
- This plugin's rules in HyperFrames
- HeyGen's own skills
- Kinocut's `hyperframes_*` tools

## License and what leaves the machine

- Apache-2.0: no headcount limit and no fee per render. Fonts, music and
  footage keep their own licenses.
- The CLI sends usage telemetry (command names, render performance), anonymous
  until `auth login` and tied to the HeyGen account after it. Set
  `HYPERFRAMES_NO_TELEMETRY=1` on every command. `telemetry disable` writes
  the same choice to `~/.hyperframes/config.json` and also takes the install
  out of canary rollouts: that one is the user's call.
- A local preview and render keep the project on the machine. Run these only
  when the user asks: `cloud render`, `share`, `publish` and the hosted MCP
  connector upload the project to HeyGen and can bill that account, and a
  cloud render's asset URLs are public to anyone who has them; `lambda` and
  `cloudrun` spend the user's own AWS or Google Cloud account.
- The scaffold loads GSAP from a CDN, and the bundled font families are fetched
  from Google Fonts (`sans-serif` became Inter that way). For an offline
  render, put the script and the font files in the project.

## Setup

```bash
export HYPERFRAMES_NO_TELEMETRY=1
hf="npx --yes hyperframes@<version>"     # the same version in every call
$hf doctor --json                        # always exits 0
$hf init my-video --skip-skills --non-interactive
```

- The first `npx` call downloads the CLI, 110 MB in the npx cache, with no
  prompt. Tell the user before it.
- Node 22 or newer, `ffmpeg` and `ffprobe`. In `doctor --json` read the
  FFmpeg, FFprobe and Chrome checks: the top-level `ok` is false while optional
  voice and music tools are missing.
- The first render downloads its own `chrome-headless-shell`, 261 MB, into
  `~/.cache/hyperframes/chrome`, even when `doctor` reports a system Chrome.
  Tell the user before it; `browser clear` removes it.
- `check` leaves a `warmCheck.js` process holding a headless Chrome (about
  300 MB) for five minutes. It exits by itself; when RAM is short, stop it by
  PID.
- Config goes to `~/.hyperframes/`, fonts and project history to
  `~/.cache/hyperframes/`, outside the project.

## The contract

What renders wrong with no error. `check --json` reports most of it with a
`Fix:` line.

- A timed element has `class="clip"`, `data-start` and `data-duration`, in
  seconds. The root's `data-duration` is the video's length: later content is
  cut.
- Each composition builds one paused timeline and registers it after its
  tweens: `window.__timelines["<data-composition-id>"] = tl`. Without it the
  render is a still frame.
- No `Date.now()`, unseeded `Math.random()`, timers, fetches or `repeat: -1`.
- Animate a child of the `.clip`, never the clip's own `display` or
  `visibility`. Start states go in `fromTo`, not in CSS.
- Never `play()` or seek media. A `<video>` is `muted` or carries
  `data-has-audio="true"`; an `<audio>` without an `id` is left out of the mix.
- A scene file in `compositions/` puts its styles, markup and script inside
  `<template>`, and its root element has `id="root"`. The host's `id` and
  `data-composition-id`, the scene root's `data-composition-id` and the
  timeline key are the same string; when they differ, each render waits 45 s
  per scene and shows static frames.
- GSAP, CSS keyframes, WAAPI, Lottie and anime.js are seeked by the renderer.
  Three.js, WebGPU, p5 and canvas draw from the `hf-seek` event
  (`e.detail.time`), never from `requestAnimationFrame`. A chart or a map
  overlay is driven from a GSAP tween's `onUpdate`, not by the library's own
  transitions.

## Loop

1. `lint` while writing, then `check --json` as the gate (lint, runtime,
   layout, contrast). "0 samples" means nothing was checked.
2. `snapshot --at 0.5,2.5` writes PNGs and a contact sheet under
   `.hyperframes/artifacts/snapshots/`. Look at them.
3. `render -o out.mp4`. The default quality encodes H.264 High;
   `--quality draft` encodes Constrained Baseline, for review only.
   `--format webm` or `mov` keeps alpha, `png-sequence` gives frames, and
   `--docker` pins Chrome and fonts when frames must match across machines.
4. `ffprobe`: the duration equals the root's `data-duration`. Then this
   skill's delivery checks, loudness included. A silent render came out with
   the index at the front (`+faststart`); the audio codec and sample rate of a
   render with sound were not checked.

## This plugin's rules in HyperFrames

- Captions and voice: each sentence start in the voice-over JSON becomes the
  `data-start` of its caption clip and of its `<audio id>`.
- Loudness: what the mix does to levels was not measured; check -16 LUFS on
  the rendered file as with any compositor.
- Formats: the canvas is the root's `data-width` and `data-height`, and scenes
  size themselves with `inset: 0`. One source in several ratios was not tried.
- Ready-made scenes: `catalog --query "<words in English>" --json` searches
  locally; `add <name>` needs the network and copies the item into
  `compositions/` as source to edit.

## HeyGen's own skills

HeyGen publishes agent skills and a Claude Code plugin with the whole format,
motion and CLI reference. Install them only when the user asks: each one tells
the agent to run `npx hyperframes events --skill=<name>` when it loads, a usage
beacon that follows the telemetry setting, and two of them (`reverse-any-video`,
`style-sampling`) are paid-plan features.

## Kinocut's `hyperframes_*` tools

They run this CLI and never call `npx`. Kinocut looks for
`MCP_VIDEO_HYPERFRAMES_COMMAND`, then `node_modules/.bin/hyperframes` from the
project upward, then `hyperframes` on PATH; with none it returns
`hyperframes_not_found`.

- `npm install --save-dev hyperframes@<version>` in the project makes them
  work (`hyperframes_info`, `hyperframes_validate`, `hyperframes_inspect` and
  `hyperframes_render` did). It adds 109 MB and edits `package.json`: ask the
  user first. Without it, use the CLI through `npx` as above.
- Kinocut runs the CLI with telemetry off. For that reason it refuses
  `hyperframes_preview` on this version and any render with `docker: true`,
  with code `hyperframes_telemetry_consent_required`. Do not set
  `KINOCUT_HYPERFRAMES_TELEMETRY=true` to get past it, which turns telemetry
  on: run `preview` or `render --docker` from the CLI instead.
- `hyperframes_validate` runs `lint` only and `hyperframes_inspect` a
  deprecated alias: gate on `check --json` from the CLI.
