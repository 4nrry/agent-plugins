# Batch 2026-11-12-compositor-default — claims

**Notes, not run records.** Why media-agent 0.25.0 makes HyperFrames the
default compositor for a new video project. Until then `video-composition`
set the two side by side and asked the user once per new project. The owner
chose HyperFrames on 2026-11-12, after the comparison below.

**The same animation in both.** 2026-11-11, RTX 4070 Laptop 8 GB, HyperFrames
0.9.35 and Remotion 4.0.543; numbers copied from the notes of the session
that built it, whose files were in a scratchpad since cleared. Three flat
characters driven by one JavaScript module, a function of time, through eight
states in 12 s; the module was shared, so the comparison is of the tooling
around it, not of the drawing. n=1, no audio.

| | HyperFrames 0.9.35 | Remotion 4.0.543 |
|---|---|---|
| Creating the project | `init`, instant, no package in the project | `create-video --blank`, 79 s, 324 MB of `node_modules` |
| The compositor's own code | 1 HTML file, 73 lines | 2 TSX files, 88 lines, and 2 type files |
| Checks before rendering | `lint` (one structure warning); `check` in 6.8 s with layout (9 samples) and contrast (20 of 20) | the template's `eslint` and `tsc`; nothing looks at the frame |
| Render, 12 s at 1920×1080, 30 fps | 12.5 s and 15.2 s | 13.3 s (45.5 s the first time, with Chrome's download) |
| File at the default settings | 2.37 MB (CRF 16) | 0.93 MB (CRF 18) |
| Two renders in a row | same sha256 | same sha256 |

The two videos were close to identical: SSIM 0.9994 averaged over the 360
frames, worst frame 0.9986. HyperFrames rendered through the system's FFmpeg
(9.0.2 that day); Remotion used the FFmpeg inside its own package.

**What decided it.**

- License: HyperFrames is Apache-2.0. Remotion is free for a person and for
  a company of up to three people; from four it needs a paid license counted
  on the whole company, not on the people who use it (`references/remotion.md`,
  read at tag v4.0.543).
- A new project is lighter, and HyperFrames checks the rendered frame before
  the final render.
- The risk taken: HyperFrames is 0.x, released several times a day (eight
  versions from 0.9.28 to 0.9.35 on 2026-11-10 and 11), and the project itself
  calls Remotion the more mature of the two and says HyperFrames breaks quietly
  when its contract is not followed (read at tag v0.9.35, not quoted in the
  references). The
  skill pins its version per project and turns its telemetry off.

**What stays.** An existing project keeps its compositor, and Remotion is
still chosen when the project is already React or shares components with an
app, or when the user names it.

**Not measured.** Audio through either compositor, a longer video, a project
with real footage, Remotion's Studio against HyperFrames' editor.
