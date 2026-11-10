---
name: cutout-animation
description: Turns a still of a character or prop into a transparent looping animation that a web page can layer over its own background — a clip made from the still, frames at stop-motion rate, the background removed from every frame, one crop box, then an animated WebP or a CSS sprite sheet. Use for an animated mascot or character on a landing page, a transparent or alpha animation for the web, a sprite sheet from an AI clip, stop-motion or claymation motion on a site, or cut-out props for layered scenery. A clip that stays a rectangle is in video-generation; one transparent PNG is in image-retouching.
---

# Cut-out animation

Video models return a rectangle with no alpha. A character that sits over a
page's own background is made in five steps, each with its own check:

still on a plain background → clip → frames → cut-out frames → one file the
page loads.

## The still and the clip

- Start from the approved still of the subject **on a plain
  background**, whole and with margin on every side. Not the scene: the
  background is removed later, and a busy one costs the edges.
- Animate it with the `video-generation` skill. Describe the motion only, lock
  the camera, say that the background does not change, and name what must not
  change: how many limbs, what it wears, no hands where it has none.
- Ask for a motion that ends close to the starting pose.
- **The clip changes the pose; the page moves the subject.** Bobbing, crossing
  the screen, following the scroll are CSS or script on the element. They cost
  no frames and change without a new clip.
- Check the clip on a frame strip (`video-generation`'s `contact-sheet.sh`)
  before removing any background. A wrong limb is cheaper to catch here.

## Choosing the loop

- **A cycle:** trim to a stretch whose first and last frames show the same
  pose (`--ss`, `--t`). Use it for a stroke that goes one way: a swim, a step,
  a wave.
- **Ping-pong:** play a short stretch forward and back (`--pingpong`). It
  halves the frames to cut out. Use it for sway, breathing and floating, not
  for a directional stroke, which reads wrong in reverse.
- **10 to 12 frames per second.** It reads as stop motion and is half the
  frames of the clip.

## Frames and cut-outs

From this skill's directory:

```bash
export COMFY_HOME=~/.local/opt/comfyui
scripts/cutout-frames.sh clip.mp4 work/octopus --fps 10 --ss 1.45 --t 3.6
python3 scripts/cutout_pack.py sheet work/octopus/cut -o check.jpg --bg '#08384C'
```

`cutout-frames.sh` extracts the frames and removes each background with the
`image-retouching` skill's headless ComfyUI. It starts the server when none is
running and stops it at the end; a second run skips frames already done.

- This removes the background with a segmentation model, which is what was
  run on a grey studio sweep with a soft shadow. A chroma key needs a solid
  key colour behind the subject, which an approved still rarely has.
- Look at `check.jpg` before packing: sample frames over the page's own
  colour. Count the limbs in every cell and look at the edges.

## Packing

```bash
python3 scripts/cutout_pack.py pack work/octopus/cut -o octopus.webp --width 400 \
    --still octopus-still.webp
python3 scripts/cutout_pack.py pack work/seahorse/cut -o seahorse.webp --pingpong \
    --sprite seahorse-sheet.webp --css seahorse-sheet.css
```

- **One crop box for the whole clip**, the union of every frame's box. Cropped
  frame by frame, the subject jitters.
- Faint alpha is dropped (`--alpha-floor`): it is what the model leaves of the
  studio shadow.
- Pick the format by what the page does with it; the three options and their
  markup are in [references/web-formats.md](references/web-formats.md). An
  animated WebP is one file with no playback control; a sprite sheet with
  `steps()` can be paused, sped up or tied to the scroll.
- Always write the still. The page shows it under `prefers-reduced-motion`.
- Report the weight of every file: `pack` prints it.

## Scenery from one image

Generate several props in one image, side by side on a plain background, not
touching. Remove the background once, then cut one file per prop:

```bash
python3 ../image-retouching/scripts/comfy-run.py background props.png -o props-cut.png
python3 scripts/cutout_pack.py split props-cut.png -o props --names kelp1,kelp2,kelp3
```

`split` refuses when the count of props it finds differs from the names
given: two props that touch come out as one.
