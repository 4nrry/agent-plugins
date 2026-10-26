# Remotion

Checked against the docs on 2026-10-26 (latest release 4.0.538).

## License

Free for individuals and companies with up to 3 employees; beyond that it is
a paid per-seat license. The FAQ says "team of up to 3", the LICENSE says
employees; whether an unsalaried co-founder counts is the user's call. State
the rule and leave the decision to whoever signs.

## Traps

- `TransitionSeries` rejects Fragment children: build scenes with `flatMap`
  returning `[<Transition/>, <Sequence/>]`.
- B-roll uses `<Video>` from `@remotion/media` (the current recommendation)
  or `<OffthreadVideo>`; never the legacy `<Video>` from `remotion`, which
  drops frames in parallel renders.
- Charts with their own animation (ECharts, Chart.js): disable it and draw the
  state at `t`, or draw on a canvas from `useCurrentFrame`.
- `dangerouslySetInnerHTML` on every frame empties the scene in multi-tab
  renders; set it once on mount, or port to components.
- Captions: a scene declares `vo: {id, at}`; the film computes the absolute
  start minus transition overlap, and the same table feeds the sentence
  `<Audio>`, the caption track and the music ducking.
- `fade()` overlaps two scenes for T frames, so two titles show at once. Wrap
  each scene's content (except the first) in `<Sequence from={T} layout="none">`
  (Remotion 4; `layout="none"` throws from 5.0).
- `Config.setRspack(true)` speeds bundling. An `@` alias into a sibling UI
  package with Tailwind v4 needs its `theme.css` imported at the root and
  `npm ci` in that package, or components render unstyled with no error.

## 3D with `@remotion/three`

A React Three Fiber scene driven by `useCurrentFrame`. Working component with
spin and dolly: [glb-turntable.tsx](glb-turntable.tsx).

- `--gl=swangle` renders empty frames with no error; use `--gl=angle` or
  `--gl=vulkan`. The Studio preview hides this (the browser has a GPU).
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
