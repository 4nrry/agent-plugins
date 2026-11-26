---
name: video-composition
description: Builds a marketing video as code from its source project — frame-driven scenes, captions from the voice JSON, b-roll placement, ducked music, real-time 3D, and 16:9, 1:1, 9:16, 4:5 plus a carousel from one source. Use for an institutional video, a short vertical video (Reels, Shorts, TikTok), code-drawn motion graphics, LinkedIn formats, declaring AI at upload, Remotion, HyperFrames, a Three.js stage with whips, motion blur and impacts, or HTML rendered to video.
---

# Video composition as code

Change a voice-over sentence and re-render only the layers it touches; one
source, every format. The
traps do not show in the preview. The rules below hold for any compositor;
each one's commands, license and traps are in its reference.

## Choose the compositor

| | HyperFrames (default) | Remotion |
|---|---|---|
| Source | HTML files with a paused timeline the renderer seeks | React components, each a function of the frame |
| License | Apache-2.0 | paid for a company of four or more people |
| Preview | a browser editor on the same files | Studio, whose visual edits are written back to the code |
| Installs | one pinned package in the project | a Node project with a bundler |
| Fits when | any new project, and a source that is HTML, a site or a design export | the project is already React, or shares components with an app |
| Reference | [hyperframes.md](references/hyperframes.md) | [remotion.md](references/remotion.md) |

- An existing project keeps its compositor.
- A new one uses HyperFrames, unless the request names Remotion or the
  project is already React or shares components with an app.
- Before installing Remotion for a company of four or more people, say that
  it needs a paid license; whoever signs decides.
- Either one downloads its own headless Chrome on the first render.
- Read the reference's license section before writing a scene.
- Each vendor publishes its own plugin (`hyperframes`, `remotion`). When it is
  installed, load its skills for how to write a scene and run the CLI. This
  skill and its references decide the rest and win where the two disagree: no
  telemetry, and no sign-in, upload of the project or paid call the user did
  not ask for; media from this plugin's other skills; the delivery checks
  below.

## Rules for any compositor

- **Everything is a function of the frame.** Anything that animates on its own
  (CSS transitions, chart libraries, `<video>` playback) breaks a frame-by-frame
  render: disable it and draw the state at frame `t`. HyperFrames seeks GSAP,
  CSS keyframes, WAAPI, Lottie and anime.js itself; canvas and Three.js there
  draw from its seek event.
- **Captions come from the voice-over JSON** (`voice` skill), not from
  transcription. One table of sentence starts feeds the voice track, the
  caption track and the music ducking. Word-level times, for captions that
  follow the voice word by word, come from aligning that text to the audio
  (`audio` skill).
- **Audio levels:** each sentence at -16 LUFS before assembly, music ducked
  under the voice (about 11 dB under it, 9 to 14 dB, in the `herk-edit-kit`
  playbook) and back up when it ends, and `loudnorm` at -16 LUFS on the
  final file; the render does not normalize.
- **Footage:** stock b-roll and photos need a license per item
  (`stock-media` skill for the rule; its `scripts/media-search.py` searches
  Pexels, Pixabay and Openverse). Download at 1080p30: re-encoding 4K at
  render time costs more. Generated shots come from the `video-generation`
  skill.
- **3D:** a pre-rendered turntable (`3d-turntable` skill) looks best for the
  product hero shot and takes minutes. A real-time Three.js stage takes
  seconds and can carry a whole piece of objects, type and interface: one
  camera with whips instead of cuts, motion blur, impacts and the hand-off
  from 3D to HTML are in [references/threejs.md](references/threejs.md).
  Scripted Blender sets with characters are the `3d-scenes` skill; their
  plates come in here, and a tape look over them is in
  [references/lofi-look.md](references/lofi-look.md).

## Build in layers

Post-production keeps picture and sound apart until the end: films and series
deliver dialogue, music and effects as separate stems (DME, Netflix's
[M&E guidelines](https://backlothelp.netflix.com/hc/en-us/articles/360057558533-M-E-Creation-and-Delivery-Guidelines-for-Nonfiction)),
a textless master beside the texted one
([Discovery](https://pmd.discovery.com/textless-material/)), and light changed
in comp without rendering the 3D again
([Foundry](https://foundry.com/insights/film-tv/animated-creations-nuke)).
Build the same way:

| Layer | Reads | A change here re-runs |
|---|---|---|
| 3D or plates | sets, camera, frames | plates, picture, mux |
| Picture | plates, text, captions, timing | picture, mux |
| Sound mix | voice, music and effects stems, levels, cues | mix, mux |
| Mux | the picture and the mix | mux |

- **Render the picture silent.** Keep voice, music and effects as separate
  stem files, mix them into one track, and mux last:
  `ffmpeg -i picture.mp4 -i mix.wav -map 0:v -map 1:a -c:v copy -c:a aac -b:a 192k -af apad -t <picture duration> -movflags +faststart out.mp4`.
  `-c:v copy` does not re-encode the picture. Pad or cut the sound to the
  picture with `-af apad -t`, not `-shortest`, which can drop the last frames
  of a copied stream.
- **Cache each layer by a fingerprint of only what it reads**: a hash of the
  spec fields and input files that layer uses, not the whole spec's mtime. An
  effect moved by a word re-runs the mix and the mux; a caption fix re-runs
  the picture and the mux, never the 3D.
- **Keep a clean picture** (plates composed with no text) when the plates are
  expensive or rendered somewhere else, such as a rented GPU, so a wording
  change composes over it instead of rendering the 3D again.
- **A freshness check or gate compares per-layer fingerprints.** One stamp
  for the whole build forces a full re-render when only the sound changed.

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
  Score candidate opening lines before production on the 5 checks of
  `hookscore.py` (MIT `4nrry/instagram-agent-skill`): sayable in under 3 s, a
  concrete marker, something at stake, the payload at the front, and a viewer
  to aim it at; a greeting or preamble costs points. The script's word lists
  are English, so for pt-BR apply the checks by hand; upstream it separated
  good hooks from bad well (AUC 0.83) but one creator's hits from misses
  barely (0.56).
- **Visual direction by act & contact-sheet juror critique** (MIT
  `4nrry/claude-code-video-toolkit`): change background field only on narrative
  act turns, ensure neighbouring acts differ clearly in **lightness**
  (light/mid/dark) so cuts do not flicker, reserve **one data accent** colour
  for the spoken highlight, and audit the contact sheet at phone size for
  1-second focal hierarchy, at most 5 type sizes, a `28 px` phone floor at
  `1080p`, and zero generic gradients, glows, or identical-tile rows.
- **Pacing.** The first visual change lands within about a second, on a strong
  word. Lists and demos cut every 1–2 s, one item per shot on its spoken word;
  an argument holds its proof (screen, report, number) as long as the voice is
  on it, often 4–8 s.
- **Everything moves.** A still enters as the first frame of a generated clip,
  a slow pan or a card that builds, never held static. Fill time with story,
  not idle loops (breathing, floating): pause at any second and something is
  arriving, moving or counting. Leave 0.3–0.75 s of stillness between an
  action and its result.
- **Cuts.** Two or three transition types per piece, repeated.
  [references/motion.md](references/motion.md) gives punch-ins, whips and
  slammed text with their sounds, frame by frame. A clip shorter
  than its slot holds its last frame instead of looping. Reject stock clips
  with their own captions or kinetic text: their words flash on screen.
- **Word-anchored inserts and J-cuts.** When adapting a reference video's
  structure, clock seconds change with the new script: bind every B-roll
  cutaway, context card, prop pop-in and sound hit to its **spoken trigger
  word** (from the aligned word table), not a fixed timestamp. Let a B-roll or
  top split-screen insert enter on its trigger word near the end of one
  speaker's turn and hold for `0.5–1.0 s` over the start of the next speaker's
  turn (**J-cut**) before cutting to the new speaker's reaction. Give context
  inserts a contrasting visual language (real screen capture, clean graphic
  card, real photography) rather than repeating the host shot's look.
- **Captions.** They carry the voice; emphasis (an accent color, a box) is rare:
  the product name or the one number, never two at once. Never over a mouth or
  chin, and never under the platform's buttons. For a talking-head short, the
  `herk-edit-kit` playbook (MIT) measured on its author's reels: 1 to 3 words
  per chunk split on phrase boundaries, hard swaps that appear 2 frames before
  the first word, one boxed look for the whole reel, and the first 2.5 s
  checked frame by frame for anything over the mouth.
  Seventeen caption looks as numbers, with chunking, timing, size and
  contrast rules: [references/caption-styles.md](references/caption-styles.md).
- **Call to action.** The written call lands with the spoken one. In a
  25 s ad broken down frame by frame, it came 2.4 s after the words, and the
  end card ran 3.3 s with no voice.
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
- Run the `video-editing` skill's `scripts/breakdown.py` on the render: hard
  cuts, each flash against its sound in frames, each word's frame, and a
  sheet of consecutive frames around every change. The same script breaks
  down a reference video before you copy what it does.
- Encode H.264 High, `yuv420p`, AAC at 48 kHz, `-movflags +faststart`, at the
  frame rate the piece was made in, and check the platform's length cap
  (`references/short-form.md`).
