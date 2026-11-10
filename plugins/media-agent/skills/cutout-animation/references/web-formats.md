# What the page loads

Three ways to put a transparent animation on a page. Sources were read on
2026-11-10.

| Format | Files | Playback control | Use it when |
|---|---|---|---|
| Animated WebP | 1 | none: it loops from load | the animation only has to run |
| Sprite sheet + CSS `steps()` | 1 image + a few CSS rules | pause, rate, scrub with the scroll | script or scroll drives the frames |
| Video with alpha | 2: VP9 WebM, and HEVC with alpha for Safari | the `<video>` API | the clip is long or large on screen |

Chrome plays VP9 with alpha and not HEVC with alpha; Safari is the reverse, so
alpha video needs both files and a `<video>` with two sources
([Rotato, transparent videos for the web](https://rotato.app/blog/transparent-videos-for-the-web)).
Neither script here writes alpha video.

## Animated WebP

```html
<picture>
  <source media="(prefers-reduced-motion: reduce)" srcset="octopus-still.webp">
  <img src="octopus.webp" alt="" width="400" height="406" loading="lazy">
</picture>
```

- `width` and `height` are the packed size, so the layout does not shift.
- `loading="lazy"` on anything below the first screen.
- Decorative: `alt=""`. When the animation is the content, describe it.

## Sprite sheet

`cutout_pack.py pack CUTDIR -o octopus.webp --sprite octopus-sheet.webp --css octopus-sheet.css`
writes a grid beside the animated WebP, and the rules that play it: one
`steps()` animation across the columns and one down the rows.

```html
<link rel="stylesheet" href="octopus-sheet.css">
<div class="octopus-sheet" role="img" aria-label="An octopus swimming"></div>
```

- The class is the sheet's file name without the extension, and the CSS
  points at `<name>.webp` beside it. So the name has to work as a class:
  letters, digits, `-` and `_`, not starting with a digit; `pack` refuses
  anything else.
- The two durations are whole milliseconds and the long one is an exact
  multiple of the short one, so the rows and columns stay in phase.
- The grid has to be full for two `steps()` animations to stay in phase. When
  the frame count has no divisor that fits WebP's 16383 px side, the last
  frame is held to fill the grid; `pack` says how many times.
- To drive the frames from script, pause the two animations and set their
  `currentTime`: `el.getAnimations().forEach(a => { a.pause(); a.currentTime = ms })`.
- The CSS turns the animation off under `prefers-reduced-motion`; the element
  then shows frame 1.

The same route as a published skill, with a chroma key in place of
segmentation: [claude-skill-klingai-animation](https://github.com/TamerinTECH/claude-skill-klingai-animation).

## Moving the element

The frames change the pose. Everything else is on the element:

```css
.float { animation: float 6.5s ease-in-out infinite }
@keyframes float {
  0%, 100% { transform: translateY(-34px) rotate(-3deg) }
  50%      { transform: translateY(34px) rotate(3deg) }
}
@media (prefers-reduced-motion: reduce) { .float { animation: none } }
```

Put the float on a wrapper and the scroll-driven transform on its parent, so
the two do not overwrite each other's `transform`.
