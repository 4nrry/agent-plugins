# HTML + headless Chrome + ffmpeg

The route written by hand, for when nothing may be installed beyond
Playwright: a `comp.html` with a `seek(t)` that places everything at time `t`,
Playwright capturing one PNG per frame across tabs, and
`ffmpeg -f image2pipe` encoding. It is deterministic and has no license.

HyperFrames ([hyperframes.md](hyperframes.md)) is the same idea as a
maintained tool, with a linter, a layout check and an audio mix. This route
has none of those: every check is yours to write.

What you lose against Remotion and HyperFrames:

- The interactive preview.
- The audio mix: build it with `ffmpeg` `amix` and `adelay` from the
  voice-over JSON instead.
- `<video>` b-roll: headless Chrome does not step video frames reliably, so
  extract the clip to PNGs first and show frame `t`.
