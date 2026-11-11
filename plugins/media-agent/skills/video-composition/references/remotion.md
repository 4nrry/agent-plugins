# Remotion

Checked against the repository at tag v4.0.543 on 2026-11-11; 5.0 is not
released. What was run is in the
[2026-11-11 record](https://github.com/4nrry/agent-plugins/blob/main/bench/plugins/media-agent/results/2026-11-11-hyperframes-remotion-CLAIMS.md).

## License

Source-available, not open source. Free for an individual, a for-profit
organization of up to 3 people, and a non-profit. From 4 people it needs a
Company License:

- **Creators:** $25 a month for each person who writes Remotion code, by hand
  or through an agent.
- **Automators:** $0.01 per render with a $100 a month minimum, when the
  company owns code that calls `npx remotion render` or `still`, a `render*()`
  API, or uses `<Player>`. A scripted pipeline is an automation.

The count is the whole company, not the people who use Remotion. An agency
that delivers only the mp4 does not add its client's people. The LICENSE says
employees, the FAQ people and the terms all personnel; whether an unsalaried
co-founder counts is the user's call, and 5.0 will count contractors. State
the rule and leave the decision to whoever signs. Licenses are bought at
`remotion.dev/pricing`.

## Traps

- B-roll and sound use `<Video>` and `<Audio>` from `@remotion/media`, or
  `<OffthreadVideo>`; never the legacy `<Video>` from `remotion`, which drops
  frames in parallel renders.
- Charts with their own animation (ECharts, Chart.js): disable it and draw the
  state at `t`, or draw on a canvas from `useCurrentFrame`. GSAP timelines go
  through `@remotion/gsap`, which seeks them.
- `dangerouslySetInnerHTML` on every frame empties the scene in multi-tab
  renders; set it once on mount, or port to components.
- Captions: a scene declares `vo: {id, at}`; the film computes the absolute
  start minus transition overlap, and the same table feeds the sentence
  `<Audio>`, the caption track and the music ducking.
- `fade()` overlaps two scenes for T frames, so two titles show at once. Wrap
  each scene's content (except the first) in `<Sequence from={T} layout="none">`.
  5.0 drops `layout="none"` on `<TransitionSeries>` itself, not on `<Sequence>`.
- `TransitionSeries` flattens Fragment children in 4.0.543. On an older pinned
  version that rejects them, build the scenes with `flatMap` returning
  `[<Transition/>, <Sequence/>]`.
- A composition with no audio renders an mp4 with no audio stream: check the
  streams before a merge that expects one.
- `Config.setRspack(true)` speeds bundling. An `@` alias into a sibling UI
  package with Tailwind v4 needs its `theme.css` imported at the root and
  `npm ci` in that package, or components render unstyled with no error.
- A minimal project is about 250 MB of `node_modules`, and the first render
  downloads Chrome Headless Shell (102 MB, 243 MB on disk) into
  `node_modules/.remotion`. Tell the user before it.
- A local render reports nothing unless a license key is set. Rendering in the
  browser with `@remotion/web-renderer` always reports to Remotion.

## Studio and the paid editor products

- `npx remotion studio` previews the composition. Its visual edits (move,
  scale, rotate, keyframes, easing) are written back to the source files:
  after the user edits there, read the files again before changing them.
- `<Track name="…">` puts clips on one timeline row. Clips on a track must not
  overlap or it throws; two things on screen at once go on separate tracks.
- Editor Starter ($600 once) and Timeline are paid templates for building an
  editor product for end users. Neither edits a video: do not suggest them for
  making one.

## For agents

- Remotion publishes its own skills (`npx remotion skills add`, written to
  `.agents/skills`) and a Claude Code plugin. Install them only when the user
  asks.
- Any docs page comes back as Markdown with `.md` appended to its URL.
- The hosted Remotion MCP server was shut down on 2026-10-26: remove
  `remotion-documentation` from an MCP config that still lists it.

## 3D with `@remotion/three`

A React Three Fiber scene driven by `useCurrentFrame`. Working component with
spin and dolly: [glb-turntable.tsx](glb-turntable.tsx).

- `--gl=swangle` renders empty frames with no error; use `--gl=angle` or
  `--gl=vulkan`. The Studio preview hides this (the browser has a GPU). The
  4.0 default lets Chrome decide; 5.0 will default to `angle`.
- Load the GLB outside `ThreeCanvas` and pass it as a prop; call
  `continueRender` only after R3F's `advance()` with the model in the scene.
- Keep lights outside the spinning group, and derive camera `near` and `far`
  from the bounding box: GLB units vary.

## Formats and stills

- A `Film` receives `fmt = fmtOf(w, h)`; scenes read `fmt.portrait`,
  `fmt.y(px)` and `fmt.f(px)`.
- Carousel: render each slide with `remotion still --frame i`; `magick` joins
  them into a PDF.
- Contact sheet: `remotion still` at chosen frames plus `magick montage`.
