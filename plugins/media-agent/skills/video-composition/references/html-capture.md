# HTML + headless Chrome + ffmpeg

The license-free route: a `comp.html` with a `seek(t)` that places everything
at time `t`, Playwright capturing one PNG per frame across tabs, and
`ffmpeg -f image2pipe` encoding. It is deterministic.

What you lose against Remotion:

- The interactive preview.
- `<Audio>` ducking: mix with `ffmpeg` `amix` and `adelay` from the voice-over
  JSON instead.
- `<video>` b-roll: headless Chrome does not step video frames reliably, so
  extract the clip to PNGs first and show frame `t`.
