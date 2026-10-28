---
name: 3d-scenes
description: Builds animated 3D shots as code in headless Blender for a video or a series — scripted sets, low-poly rigged figures from a .glb, a camera that never stops, preview and final quality, cached plates, a frozen-frame check. Use for a 3D scene or animated series in Blender, a character that slides, faces the wrong way or stands in the wrong pose, EEVEE renders that take too long, re-rendering only the shots that changed, frames that came out identical, or 3D too heavy for the browser. A single product spin is in 3d-turntable.
---

# 3D scenes as code

Each set is a Python function that builds a scene and renders it as a PNG
sequence (a plate). Text, grain, captions and sound go on later in the
compositor (`video-composition` skill), so a wording change never re-renders
3D. A product spin alone is the `3d-turntable` skill; a light supporting shot
reframed for several formats is cheaper as Three.js in the compositor.

`scripts/scene_kit.py` holds the pieces below. In a scene script:

```python
import sys; sys.path.insert(0, "<this skill>/scripts")
import math, scene_kit as k
k.reset("preview", frames=120)                    # or "final"
a = k.figure("human.glb", (0, 0, 0), face=0, action="Death", frame=0)
cam, tgt = k.camera((0, -6, 1.5), (0, 0, 1), lens=30)
k.keys(cam, "location", [(1, -6), (120, -4)], 1)  # push-in from frame 1
k.shake(tgt, 0.02)
light, ltgt = k.spot((0, -3, 6), (0, 0, 0.8), energy=1500)
k.sweep(ltgt, 120)
k.render(out_dir)
```

`blender -b --factory-startup --python-exit-code 1 -P scene_kit.py -- --demo
human.glb out/` renders three figures (front, profile, back) to check a new glb.

## Running Blender

- Always pass `--python-exit-code 1`: without it Blender 5.2 exits 0 after an
  uncaught Python error and the pipeline takes an empty folder as a render.
- One Blender process per scene, in parallel. Cache each plate under a hash of
  the scene sources and skip it when the hash and the frame count match.
- On a hybrid laptop, EEVEE lands on the integrated GPU unless the process is
  offloaded: set `__NV_PRIME_RENDER_OFFLOAD=1` and
  `__GLX_VENDOR_LIBRARY_NAME=nvidia` (what `prime-run` does). Cycles device
  traps are in the `3d-turntable` skill.

## Quality

- Two tiers from the same script: `preview` (270×480, 4 TAA samples) to review
  framing and timing, `final` (540×960, 8 samples) for delivery. Upscale the
  final ×2 with nearest neighbour for 1080×1920; a grain pass then hides the
  low sample count.
- Fogged spotlight cones turn into a grid with fewer volume samples or coarse
  volume tiles. Blender 5 has no EEVEE bloom to soften them: the kit's `final`
  uses 2 px tiles. Accept the grid in `preview`.
- Encode with `h264_nvenc` when the card has it; check the result against x264
  (PSNR, SSIM) once before trusting the preset.

## Figures from a .glb

- **Rotation is ignored.** glTF roots import in quaternion mode, so writing
  `rotation_euler` does nothing and every figure faces the camera. Switch the
  root to `XYZ` first (`figure()` does).
- **Names lie.** The rest pose can be a run, and a clip called Idle can read
  as walking. Render a frame of each candidate action on a contact sheet and
  pick by eye; in the CC0 Quaternius human, frame 0 of Death is the neutral
  stand.
- **Freeze the evaluated mesh.** Applying the armature only moves the bones;
  copy the evaluated mesh and drop the modifier, or the body returns to the
  bind pose.
- **Scale by measured height** on the evaluated mesh in the chosen pose, not by
  the file's scale: pose changes height.
- **Walking** is not a frozen pose plus translation: that slides. Loop the
  rig's walk action and move the root at the clip's stride speed (distance
  per cycle over cycle length), or the feet skate.
- glbs often ship a Cube, Camera or Light beside the character; the kit removes
  them. Keep the model's license (CC0, CC-BY credit) with the project.

## Camera and light

- The camera moves from frame 1 to the last frame of the shot. Animate the
  camera and its target empty (`TRACK_TO`), never the rotation. Use linear
  interpolation when the move must not settle.
- Shake is noise on the target, added on top of any move; stronger for wide
  shots, almost none in close-up.
- Depth of field only to hide or isolate something. One spot with a slow sweep
  plus volumetric fog gives a strong look at a low cost.
- Text on a 3D object appears only when it is legible on a phone.

## Checking

- `scripts/check_motion.py PLATE_DIR` fails when two consecutive frames are
  identical. Run it on plates, before grain or text hides a still picture.
- Look at a contact sheet of every shot at phone size before the final render.

## A series

Keep a visual bible beside the scenes: cast and materials, the poses that
exist, lens range, camera moves, colours reserved for one meaning, and a
do/don't list. Every episode reuses it; a new pose or colour is a decision
recorded there first.
