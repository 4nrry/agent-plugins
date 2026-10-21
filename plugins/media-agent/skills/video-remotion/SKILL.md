---
name: video-remotion
description: Builds an institutional or marketing video as code — Remotion (React), or HTML with a deterministic timeline captured by headless Chrome and ffmpeg — with captions derived from the voice-over JSON, b-roll, ducked music, and the same film in 16:9, 1:1, 9:16 and 4:5 plus a carousel of stills. Use when a task asks for a marketing or institutional video, Remotion, React motion graphics, frame-by-frame animation, burned-in captions, LinkedIn or Instagram formats, Reels, a carousel, or whether a company may use Remotion.
---

# Video as code: Remotion, or HTML + Chrome + ffmpeg

Change a voice-over sentence and re-render; one source, four formats. The
traps do not show in the preview.

## License first

Remotion is free for individuals and companies with up to 3 employees; beyond
that it is a paid per-seat license. The FAQ says "team of up to 3", the
LICENSE says employees; whether an unsalaried co-founder counts is the user's
call. State the rule and leave the decision to whoever signs.

Without Remotion: a `comp.html` with a `seek(t)` that places everything at time
`t`, Playwright capturing one PNG per frame across tabs, and
`ffmpeg -f image2pipe` encoding. It is deterministic and license-free; you lose
the interactive preview, `<Audio>` ducking (use `amix`/`adelay`) and `<video>`
b-roll — headless Chrome does not step video frames reliably, so extract the
clip to PNGs first.

## Remotion traps

- `TransitionSeries` rejects Fragment children: build scenes with `flatMap`
  returning `[<Transition/>, <Sequence/>]`.
- B-roll uses `OffthreadVideo`, not `<Video>`, which drops frames in parallel
  renders.
- Charts with their own animation (ECharts, Chart.js) do not know frames exist:
  disable animation and draw the state at `t`, or draw on a canvas from
  `useCurrentFrame`.
- `dangerouslySetInnerHTML` on every frame empties the scene in multi-tab
  renders; set it once on mount, or port to components.
- Captions come from the voice-over JSON (`id`, `text`, `duration`, `start`),
  not transcription. A scene declares `vo: {id, at}`; the film computes the
  absolute start minus transition overlap, and the same table feeds the
  sentence `<Audio>`, the caption track and the music ducking.
- Render `--crf` does not normalize audio: run `loudnorm` at -16 LUFS on the
  final MP4 (`-c:v copy`), after normalizing each sentence (`voice-over`).
- `Config.setRspack(true)` speeds bundling; an `@` alias into a sibling UI
  package with Tailwind v4 needs its `theme.css` imported at the root and
  `npm ci` in that package, or components render unstyled with no error.
- `fade()` overlaps two scenes for T frames, so two titles show at once. Wrap
  each scene's content (except the first) in `<Sequence from={T} layout="none">`.

## 3D in the video: Three.js or Blender

`@remotion/three` renders a React Three Fiber scene driven by
`useCurrentFrame`. Blender (`turntable-blender`) takes minutes for a turn but
looks better (saturated color, soft shadows, reflections); Three.js takes
seconds and looks real-time. Use Blender for the product hero shot; use
Three.js for supporting shots where the camera follows the caption, and to
reframe one move in 16:9, 9:16 and 4:5. Working component with spin and dolly:
[references/glb-turntable.tsx](references/glb-turntable.tsx).

- `--gl=swangle` renders empty frames with no error; use `--gl=angle` or
  `--gl=vulkan`. The Studio preview hides this (the browser has a GPU).
- Load the GLB outside `ThreeCanvas` and pass it as a prop; call
  `continueRender` only after R3F's `advance()` with the model in the scene.
- Keep lights outside the spinning group.
- Derive camera `near`/`far` from the bounding box; GLB units vary.

## Formats from one source

- A `Film` receives `fmt = fmtOf(w, h)`; scenes read `fmt.portrait`,
  `fmt.y(px)` (heights scaled by `h/1920`) and `fmt.f(px)` (fonts by
  `sqrt(h/1920)`).
- 1:1 for LinkedIn: the 16:9 scaled by 0.5625 with brand-color bars.
- 4:5 for the Instagram feed needs stacking: side-by-side becomes a column.
- Reels 9:16: Instagram's UI covers the top and especially the bottom; keep
  text inside 250 px from the top and 420 px from the bottom at 1080x1920 (a
  working margin, not an official number).
- Carousel: a composition whose frame `i` is slide `i` frozen, rendered with
  `remotion still --frame i`; `magick` joins them into a PDF for LinkedIn.

## Before delivery

A 3x3 contact sheet of stills per format (`remotion still` + `magick montage`)
catches overlapping and clipped text the 50% preview hides. Check fps,
duration and resolution with `ffprobe`, and -16 LUFS with `ebur128`.
