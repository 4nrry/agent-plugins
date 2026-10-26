---
name: video-composition
description: Builds a marketing video as code — frame-driven scenes, captions from the voice JSON, b-roll, ducked music, 3D, and 16:9, 1:1, 9:16, 4:5 plus a carousel from one source. Use for an institutional video, motion graphics, burned-in captions, Reels or LinkedIn formats, or Remotion.
---

# Video composition as code

Change a voice-over sentence and re-render; one source, every format. The
traps do not show in the preview. The rules below hold for any compositor:
[references/remotion.md](references/remotion.md) covers Remotion, and
[references/html-capture.md](references/html-capture.md) the license-free
HTML + headless Chrome + ffmpeg route.

## Choose the compositor

Check its license before writing a scene: Remotion is paid above a small team
(the rule is in `references/remotion.md`; whoever signs decides). The HTML
route has no license cost and loses the interactive preview.

## Rules for any compositor

- **Everything is a function of the frame.** Anything that animates on its own
  (CSS transitions, chart libraries, `<video>` playback) breaks a frame-by-frame
  render: disable it and draw the state at frame `t`.
- **Captions come from the voice-over JSON** (`voice` skill), not from
  transcription. One table of sentence starts feeds the voice track, the
  caption track and the music ducking.
- **Audio levels:** each sentence at -16 LUFS before assembly, music ducked
  under the voice, and `loudnorm` at -16 LUFS on the final file; the render
  does not normalize.
- **Footage:** stock b-roll and photos need a license per item (`audio` skill
  for the rule; its `scripts/media-search.py` searches Pexels, Pixabay and
  Openverse too). Download at 1080p30: re-encoding 4K at render time costs
  more. Generated shots come from the `video-generation` skill.
- **3D:** a pre-rendered turntable (`3d-turntable` skill) looks best for the
  product hero shot and takes minutes; a real-time Three.js scene takes seconds
  and suits supporting shots and reframing one move for several formats.

## Formats from one source

- Scale layout by the frame: heights by `h/1920`, fonts by `sqrt(h/1920)`, and
  stack side-by-side elements into a column for 4:5 and 9:16.
- 1:1 for LinkedIn: the 16:9 scaled into the square with brand-color bars.
- Reels 9:16: Instagram's UI covers the top and especially the bottom; keep
  text within 250 px of the top and 420 px of the bottom at 1080x1920 (a
  working margin, not an official number).
- Carousel: one composition whose frame `i` is slide `i`, rendered as stills
  and joined into a PDF for LinkedIn.

## Before delivery

- A 3x3 contact sheet of stills per format catches overlapping and clipped
  text that a scaled-down preview hides.
- Check fps, duration and resolution with `ffprobe`, and -16 LUFS with
  `ffmpeg -af ebur128`.
