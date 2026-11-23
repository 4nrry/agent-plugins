# A Three.js stage in HyperFrames

Objects, type and interface in real time 3D, drawn frame by frame: a product,
a stack of cards, a logo on a set, a menu that grows out of the scene.
Figures with a rig belong to the `3d-scenes` skill (Blender).

Measured on 2026-11-17 in a 6 s, 1080×1920, 30 fps test rendered with
HyperFrames 0.9.59 and three 0.180.0 on an 8 GB laptop GPU, and in a
frame-by-frame breakdown of a 25 s vertical ad built the same way; the
[record](https://github.com/4nrry/agent-plugins/blob/main/bench/plugins/media-agent/results/2026-11-17-threejs-stage-CLAIMS.md)
has the numbers. The test composition is
[`threejs-stage/`](threejs-stage/): three books fall onto a stage with a
number and a hit each, a whip to a close-up, the narrated book lights up,
and the stack becomes a list in HTML. The copy there has its text moved
inside every platform's safe zone and the list held to 7.3 s; the canvas is
the one measured. It needs `assets/vendor/three.min.js` (three 0.180.0 as one
ES module; HyperFrames' `path-traced-3d` example vendors one, MIT) and a
`sfx.wav` (the test's: `sfx-synth.py slam` at 1.0, 1.6 and 2.2 s). It tests
techniques; a real piece would not open on an empty stage.

## Contents
- Wiring
- One camera, whips instead of cuts
- Motion blur
- Look
- Beats
- From 3D to HTML
- Check

## Wiring

The contract is in [hyperframes.md](hyperframes.md); this is what a WebGL
stage adds to it.

- The root has `data-no-timeline`; the `<canvas>` and the text layer over it
  are clips. One module script draws both from `hf-seek`: chain each seek on
  a promise, pass that promise to `event.detail.waitUntil`, and put the setup
  promise in `window.__hf.buildReady[<key>]`. Read one pixel back after
  drawing, so the frame is finished when the seek resolves.
- `preserveDrawingBuffer: true`, pixel ratio 1, the canvas at the root's size.
- Every pose is a function of the time: camera, falls, particles (seeded
  velocities, positions in closed form), light. Nothing carries over from the
  previous seek.
- **A value set on one frame never reaches the others.** The render splits the
  frames among 2 to 6 browser workers (each run chose its own count). In the
  test, a colour sampled on the hand-off frame reached only the worker that
  drew that frame, and the bars came out black in every other one. Compute
  what later frames need in setup, from a render of that time.
- Fonts: the compiler fetches named families from Google Fonts and swaps some
  (`Georgia` came out as EB Garamond). Name the family, `await
  document.fonts.load()` in setup, and only then draw a `CanvasTexture` with
  it, so the texture and the HTML use the same letters.
- Repeat renders were not bit-identical: 39 to 63 of 180 frames differed,
  the worst at 50.1 dB PSNR (no visible difference), and the audio was
  identical. With the sparks never culled, two renders of the final copy
  still differed in 56 of 219 frames, so culling is not the cause. Compare renders by PSNR, not by `sha256`.

## One camera, whips instead of cuts

The reference ad has no hard cut in 25 s (`breakdown.py`, whose thresholds
were tuned on that ad: 0 cuts, 14 change zones): every change of shot is a
camera move.

- Shots are `(position, target)` pairs. Inside a shot the camera drifts
  linearly; between shots it whips with an ease-in-out in 4 to 5 frames, as
  in the reference (the test used 5).
- Text leaves 2 frames before a whip and the next line enters on its word
  after it.

## Motion blur

Page motion blur (`data-motion-blur`, in hyperframes.md's tool notes) blurs
HTML elements that move. A camera move inside a WebGL canvas moves no element,
so blur it in the draw:

1. Render the scene at N times spread over the shutter (180°: half a frame,
   centred on the frame time) into a half-float target with 4× MSAA.
2. Add each one to an accumulation target at weight 1/N.
3. Run bloom and tone mapping once, on the sum.

Size N by the motion. Project a few points of the set at both ends of the
shutter. When none moves 1.5 px, use 1 sample; otherwise use one per 2 px of
travel, at least 16 and at most 64. With 8 fixed samples the whip showed
stepped copies (test frame 84), the same steps visible in the reference's
falls and whips (its frames 160 and 252). Sized samples drew a smooth streak.

Cost, with 4 workers on a machine loaded by other work (load average 14 to
21): 11.3 and 16.5 s without blur, 20.8 and 18.5 s with sized blur, for the
6 s test. It has one whip, one pull-back and three falls; a film that moves
all the time pays more.

## Look

- Render linear HDR (half float). Bloom from a bright pass (threshold about
  1.0) blurred at half and quarter size, then ACES tone mapping and sRGB in
  the final pass only.
- Clear the bloom targets to black. The test first cleared one to the
  background colour, which the final pass then added over the whole frame:
  the dark floor read 8.7 mean luma instead of 5.2, until a review caught it.
- What blooms is what goes above 1.0: emissive labels, lit rods, additive
  rings and sparks. Keep the rest under it.
- Fog towards the background colour, a spot from above, a cold rim light.

## Beats

### An impact

On the landing frame, all at once:

| Element | Value in the test |
|---|---|
| The fall | `y = rest + 9·(1 − u²)` over 0.36 s, then a wobble `0.05·e^(−9·dt)·sin(38·dt)` |
| Flash | exposure `1 + 1.3·e^(−dt/0.06)` |
| Ring on the floor | scale 1 to 6 over 0.45 s, ease-out, opacity `(1 − u)²`, additive |
| Sparks | 56 points, seeded velocities, ballistic, 0.7 s |
| Number | in HTML, scale 1.4 to 1 over 4 frames |
| Sound | `sfx-synth.py slam` from the `audio` skill, starting on the landing frame |

`breakdown.py` found the sound 0 or 1 frame before the flash in the test
(AAC reads a hit up to one frame early; the mix put it on the frame), and 1
to 2 frames after the flash in the reference. The reference's counter counted
1-2-3-4 while the voice said "one, two, four": the count on screen may run
ahead of the words.

### Light on what the voice names

From the start of the word that names it, raise that object's emissive
intensity over 0.15 s and dim the others. In the test, 0.12 rose to 2.0 and
the rest fell to 0.03. Bring it back down before any hand-off to HTML.

### Words on their frame

Each word enters on the frame where the voice says it (word times from the
`audio` skill), with a 2-frame fade from an 8 px blur. In the reference, each
of the 18 title words checked appeared within 2 frames of its spoken start,
before or after it; the caption's word-by-word highlight came 0 to 3 frames
after the word.

## From 3D to HTML

When the scene becomes interface (a list, a menu), HTML elements take the
objects' places. The reference did it with a cross-fade and showed doubled
letters, then labels that overlapped for about half a second. In the test:

1. Square the objects to the camera and stop the camera before the swap.
2. Each frame, project the corners of each object's face and place its HTML
   element on that rectangle.
3. Use the texture's font, at the size the projected height gives.
4. Swap on one frame. A two-frame cross-fade showed both layers, and the
   letters doubled (first render, frame 136).
5. Take each element's colour from a render of the swap frame made in setup.
   Light and tone mapping change it from the material's colour. Read inside
   the canvas: a face can be wider than the frame, and a read outside it
   returned black.
6. Fly the elements to their new places in the same order, so none crosses
   another. Hide the labels during the flight and show them after it.

After all six steps the swap still jumped by 18.3 (mean absolute difference
of the grey frame, 0–255, over the band the stack fills), against 3.1 to 5.4
for the same band one frame apart in a drift or during the flight. The bloom and the
lighting gradient exist only in 3D, and the canvas and HTML text sat about
10 px apart vertically. Swap inside a move or a flash, or fade the 3D-only
light out first.

## Capture traps

From godogen's `skills/engine-guide/threejs.md` (MIT, `htdt/godogen` at
`07eaa1d`), not measured here:

- **A real GPU.** Headless Chrome falls back to SwiftShader or llvmpipe without
  a word: slow or blank frames. On Linux run under `xvfb-run` with
  `--use-angle=vulkan`, read the WebGL `RENDERER` string, and stop if it says
  `swiftshader`, `llvmpipe` or `lavapipe`.
- **WebGPU falls back too.** `WebGPURenderer` runs on WebGL2 when there is no
  adapter, with only a console warning; check
  `renderer.backend.isWebGPUBackend` before trusting a WebGPU-only effect.
- **Color maps** you load or build need `colorSpace = SRGBColorSpace`, or they
  render washed out; the glTF loader tags its own.
- **Lights are physical:** point and spot lights decay with inverse square
  (`decay = 2`), so intensities from old examples leave the far set black. A
  directional light's shadow camera spans ±5 units; size it to the set.
- **Rigged clones** need `SkeletonUtils.clone()`; `clone()` keeps the copy on
  the original's bones.

## Check

Run the `video-editing` skill's `breakdown.py` on the render. It reports the
cuts (there should be none), the change zones with their sheets, each flash
with its sound's offset in frames, and, with `--words`, each word's frame. Then look at the
zone sheets for the whips and the swap.
