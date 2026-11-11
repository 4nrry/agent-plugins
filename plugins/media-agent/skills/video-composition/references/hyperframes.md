# HyperFrames

Checked against the repository at tag v0.9.35 on 2026-11-11. What was run is
in the
[2026-11-11 render record](https://github.com/4nrry/agent-plugins/blob/main/bench/plugins/media-agent/results/2026-11-11-hyperframes-remotion-CLAIMS.md)
and the
[vendor plugins record](https://github.com/4nrry/agent-plugins/blob/main/bench/plugins/media-agent/results/2026-11-11-vendor-plugins-CLAIMS.md).

HTML, CSS and a paused animation timeline rendered to video: the renderer
seeks every frame in headless Chrome and ffmpeg encodes and mixes the audio.
HeyGen maintains it and releases several times a day (eight versions in the two
days before this check), so pin one version everywhere: 0.9.35, the one these
notes were checked on, unless the project or the installed HeyGen plugin
already pins another.

## Contents
- License and what leaves the machine
- Setup
- The contract
- Loop
- This plugin's rules in HyperFrames
- With HeyGen's plugin installed
- Kinocut's `hyperframes_*` tools

## License and what leaves the machine

- Apache-2.0: no headcount limit and no fee per render. Fonts, music and
  footage keep their own licenses.
- Telemetry stays off. The CLI otherwise sends usage data (command names,
  render performance), anonymous until `auth login` and tied to the HeyGen
  account after it. Set `HYPERFRAMES_NO_TELEMETRY=1` on every command, and run
  `telemetry disable` once per machine: it writes the choice to
  `~/.hyperframes/config.json` and takes the install out of canary rollouts.
- Never run `auth login` for the user or ask for it as a default step.
- A local preview and render keep the project on the machine. Run these only
  when the user asks, and say what they cost first: `cloud render`, `share`,
  `publish` and the hosted MCP connector upload the project to HeyGen and can
  bill that account, and a cloud render's asset URLs are public to anyone who
  has them; `lambda` and `cloudrun` spend the user's own AWS or Google Cloud
  account.
- The scaffold loads GSAP from a CDN, and the bundled font families are fetched
  from Google Fonts (`sans-serif` became Inter that way). For an offline
  render, put the script and the font files in the project.

## Setup

```bash
export HYPERFRAMES_NO_TELEMETRY=1
npx --yes hyperframes@<version> init my-video --skip-skills --non-interactive
cd my-video
npm install --save-dev hyperframes@<version>   # the project's own copy
npx hyperframes telemetry disable               # once per machine
npx hyperframes doctor --json                   # always exits 0
```

- The project carries the CLI as a dependency: 109 MB in `node_modules`, and
  the version is in `package.json`. `npx hyperframes` inside the project and
  Kinocut's tools both use that copy. Tell the user the size before the first
  install on a machine; the `npx --yes` call for `init` adds 110 MB to the npx
  cache.
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

## With HeyGen's plugin installed

Its `hyperframes`, `hyperframes-cli` and `hyperframes-registry` skills hold
the whole format, CLI and catalog reference: load them to write scenes. Where
they and this plugin disagree, this plugin wins:

- Skip the usage beacon each skill opens with (`events --skill=<name>`) and
  the `feedback` call after a render.
- Its `media-use` skill asks for a HeyGen sign-in whenever a request needs
  HeyGen's catalog or models, plans with no cheaper or free substitute, and
  says not to volunteer prices. Here the order is the reverse: voice, music,
  effects, stock and generated shots come from this plugin's `voice`, `audio`,
  `stock-media`, `image-generation` and `video-generation` skills. A HeyGen
  sign-in or credit is used only when the user asks for it, with the price
  said first.
- `reverse-any-video` and `style-sampling` need a paid plan.
- It runs the CLI through its own launcher
  (`skills/hyperframes/scripts/plugin-cli.mjs` under the plugin root), at the
  plugin's version and not the project's copy. Keep the project's
  `hyperframes` dependency at that version, so the launcher and Kinocut run
  the same CLI.
- The plugin does not update itself: updating it is the user's step, and the
  project's dependency moves with it.

## Kinocut's `hyperframes_*` tools

They run the project's copy of the CLI and never call `npx`. Kinocut looks
for `MCP_VIDEO_HYPERFRAMES_COMMAND`, then `node_modules/.bin/hyperframes` from
the project upward, then `hyperframes` on PATH; with none it returns
`hyperframes_not_found`.

- With the dependency from Setup, `hyperframes_info`, `hyperframes_validate`,
  `hyperframes_inspect` and `hyperframes_render` worked.
- Kinocut runs the CLI with telemetry off. For that reason it refuses
  `hyperframes_preview` on this version and any render with `docker: true`,
  with code `hyperframes_telemetry_consent_required`. Do not set
  `KINOCUT_HYPERFRAMES_TELEMETRY=true` to get past it, which turns telemetry
  on: run `preview` or `render --docker` from the CLI instead.
- `hyperframes_validate` runs `lint` only and `hyperframes_inspect` a
  deprecated alias: gate on `check --json` from the CLI.
