---
name: 3d-turntable
description: Renders a 360-degree turntable of a .glb or .gltf product model as transparent PNG frames for video, in headless Blender with Cycles on the GPU. Use for a pre-rendered product spin, a device turntable, headless Blender, Cycles, CUDA or OptiX, or Blender segfaulting on devices. Real-time 3D in the composition is in video-composition.
---

# Turntable of a .glb in headless Blender

The bundled script imports the glb, centers it on its bounding box, places a
3/4 camera and three area lights, and renders one full turn. From this skill's
directory:

```bash
blender -b -P scripts/turntable.py -- --glb model.glb --out /path/frames --frames 120 --samples 128 --res 1080
```

`--preview` renders 3 frames at 16 samples to check framing and light first.
120 frames at 30 fps is a 4 s turn; use only the stretch the scene needs.

For a moving camera instead of a spinning model, or the same move in several
formats, use Three.js in the compositor (`video-composition` skill): seconds instead
of minutes, with visibly poorer lighting.

## What breaks without a useful error

- **`prefs.get_devices()` segfaults** on machines with an integrated Intel Arc
  beside an NVIDIA GPU (oneAPI enumeration). `get_devices_for_type("CUDA")` or
  `"OPTIX"` enumerates only that backend; the script does this, and
  `CYCLES_BACKEND=OPTIX` forces OptiX. If OptiX returns no device (driver and
  Blender version must match), it falls back to CUDA.
- **Blender 5 has no `action.fcurves`** (layered actions). For a linear spin,
  set `preferences.edit.keyframe_new_interpolation_type = "LINEAR"` before
  inserting keyframes.
- **Overexposure:** area-light watts scale with area; "reasonable" values blow
  out a 30 cm object. The script uses 60/22/55 × size² for key/fill/rim, with
  size the model's largest dimension, and AgX Base Contrast.
- **Transparent PNG** needs both `film_transparent = True` and
  `color_mode = "RGBA"`, or the background comes out grey.
- **Light backgrounds:** premultiplied alpha shows a white halo in some
  compositors; in HTML/Remotion, `mix-blend-mode` on a transformed container
  needs `isolation: isolate` on its parent.

Untested: several transmissive (glass) materials under AgX; Blender below 4.x.
