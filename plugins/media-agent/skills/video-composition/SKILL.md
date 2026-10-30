---
name: video-composition
description: Builds a marketing video as code from its source project — frame-driven scenes, captions from the voice JSON, b-roll placement, ducked music, real-time 3D, and 16:9, 1:1, 9:16, 4:5 plus a carousel from one source. Use for an institutional video, a short vertical video (Reels, Shorts, TikTok), code-drawn motion graphics, LinkedIn formats, declaring AI at upload, Remotion, Three.js, or HTML rendered to video.
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
  Scripted Blender sets with characters are the `3d-scenes` skill; their
  plates come in here, and a tape look over them is in
  [references/lofi-look.md](references/lofi-look.md).

## Formats from one source

- Scale layout by the frame: heights by `h/1920`, fonts by `sqrt(h/1920)`, and
  stack side-by-side elements into a column for 4:5 and 9:16.
- 1:1 for LinkedIn: the 16:9 scaled into the square with brand-color bars.
- 9:16: each platform's buttons and caption cover the edges, the bottom most
  and the right side on all of them. Keep text and logos inside the safe zone
  in [references/short-form.md](references/short-form.md).
- Carousel: one composition whose frame `i` is slide `i`, rendered as stills
  and joined into a PDF for LinkedIn.

## Short vertical video (Reels, Shorts, TikTok)

The feed decides in the first seconds, and many viewers start with the sound
off.

- **Opening.** Frame 0 is the strongest frame: no fade from black, no logo
  intro. The hook is on screen as text from that frame, not only spoken. Open
  one question in the first 3 seconds and answer it before the end; two hooks
  weaken each other. When it fits, end on the opening image so a replay flows.
- **Pacing.** The first visual change lands within about a second, on a strong
  word. Lists and demos cut every 1–2 s, one item per shot on its spoken word;
  an argument holds its proof (screen, report, number) as long as the voice is
  on it, often 4–8 s.
- **Everything moves.** A still enters as the first frame of a generated clip,
  a slow pan or a card that builds, never held static. Fill time with story,
  not idle loops (breathing, floating): pause at any second and something is
  arriving, moving or counting. Leave 0.3–0.75 s of stillness between an
  action and its result.
- **Cuts.** Two or three transition types per piece, repeated; punch-ins,
  whips, slammed text and their sounds, in frames, are in
  [references/motion.md](references/motion.md). A clip shorter
  than its slot holds its last frame instead of looping. Reject stock clips
  with their own captions or kinetic text: their words flash on screen.
- **Captions.** They carry the voice; emphasis (an accent color, a box) is rare:
  the product name or the one number, never two at once. Never over a mouth or
  chin, and never under the platform's buttons.
- **Test the opening.** Render two or three openings (only the hook changes,
  which code makes cheap) and post them as tests to people who do not follow
  the account; keep the one that holds. Compare with the account's own median:
  no platform publishes a good skip rate.
- **A series** from one template still needs its own story and pictures each
  episode: platforms demote and demonetize repetitive, template-made posts.
- **Declare AI** at upload when any shot, image or voice is realistic and
  generated ([references/short-form.md](references/short-form.md)).

## Before delivery

- A 3x3 contact sheet of stills per format catches overlapping and clipped
  text that a scaled-down preview hides.
- Measure every string with the font and size that will draw it, against
  the safe zone, and fail the build when one spills; a longer headline in the
  next episode is caught before rendering. Put one frame under a screenshot of
  the platform's interface from a phone to see what the buttons cover.
- Check fps, duration and resolution with `ffprobe`, and -16 LUFS with
  `ffmpeg -af ebur128`.
- Look at frame 0 on its own, at phone size: it is what the feed shows.
- Encode H.264 High, `yuv420p`, AAC at 48 kHz, `-movflags +faststart`, at the
  frame rate the piece was made in, and check the platform's length cap
  (`references/short-form.md`).
