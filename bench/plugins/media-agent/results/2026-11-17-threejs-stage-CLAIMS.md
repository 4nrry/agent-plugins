# Batch 2026-11-17-threejs-stage — claims

**Notes, not run records.** Why media-agent 0.26.0 adds three things:

- `video-composition/references/threejs.md`, with its test composition in
  `references/threejs-stage/`;
- `video-editing/scripts/breakdown.py`;
- short rules in `video-composition` (word times for kinetic text, the call
  to action, music after the voice).

Each one came from a frame-by-frame reading of one ad. One render test and
three clips check them; the files were not kept beyond this session's
scratchpad except where a hash is given.

**Machine.** Linux x86-64, 22 threads, 30 GB RAM, an RTX 4070 Laptop GPU with
8 GB, Node 26.13.1, ffmpeg n9.0.2, numpy 2.4.6, Pillow 12.3.0. HyperFrames
0.9.59 run through HeyGen's plugin launcher (`plugin-cli.mjs`, from the npx
cache), its `chrome-headless-shell` 152.0.7977.30, beginframe capture, which
reported "hardware gpu". three 0.180.0 from the bundle HyperFrames vendors in
its `path-traced-3d` example (sha256 `a247cb7f…21fc9`, not in this repo:
historical). The machine was
running other work: load average 14 to 21.

## The ad read frame by frame

A 25 s, 1080×1920, 30 fps vertical ad for a Bible app, posted on X on
2026-11-12. Its author said a model that writes code made it (sha256 of the
downloaded file `cceca66b…7212d`, not in this repo: historical). All 751 frames were extracted, sheets were
made of every change, and the voice was transcribed with word times
(WhisperX large-v3).

- No hard cut. Every change of shot is a camera whip of 4 to 5 frames or a
  slower move.
- The motion blur on falls and whips is a stack of sharp copies (frames 160
  and 252), the look of averaging a few sub-frame renders. Blender's motion
  blur draws a smooth streak.
- At frame 544 the 3D books turn into flat rectangles with web-font text, the
  letters doubled. From 552 to 560 the rectangles overlap with their labels
  jumbled. The interface after it is vector HTML.
- From these the references say "most likely" a WebGL scene under HTML,
  rendered frame by frame. Pixels do not name the library or the renderer.
- Four book landings: each one's flash, ring, sparks and number on one frame,
  with the low hit 1 to 2 frames later. The on-screen count ran 1-2-3-4
  while the voice said "one, two, four".
- Each of 18 title words checked appeared within 2 frames of its spoken start;
  the caption highlight came 0 to 3 frames after its word.
- The written call to action came 2.4 s after the spoken one. The end card
  ran 3.3 s with no voice, while the music rose from about −20 to −24 dB RMS
  between lines to −9.5 dB.
- −14.7 LUFS integrated, true peak −1.4 dBFS.

## `breakdown.py`

Three clips, the rules tuned on them; not tried on any other.

| Clip | Read by eye or built | Script |
|---|---|---|
| The ad | 0 cuts, 4 impact flashes (f125, f162, f195, f201) | 0 cuts, 14 change zones, the 4 flashes with low hits at +1, +2, +1, +1 frames; about 9 s, 228 MB peak |
| Synthetic, 6 s | a hard cut at f90 (testsrc2 to mandelbrot); a flash at f120 that whites the frame out; a 55 Hz thump at f121 | the cut at f90; the flash at f120; its hit read at f120 |
| The Three.js test below | 3 flashes, no cut | 3 flashes, 0 cuts, hits at −1, 0, 0 frames |

What the tuning changed, version by version:

1. The first version called the ad's first flash a cut. It also called two
   whips onto brighter shots and a fade to a white card flashes.
2. A structure test (zero-mean, unit-spread correlation of 45 px wide
   thumbnails) fixed those, but called the synthetic whiteout a cut.
3. A flash is now light that rises and falls back, with the same picture
   kept or back afterwards, compared both with the frame before the rise and
   with the one before the jump.

Sound frames read up to one frame early: the synthetic thump starts at f121
and read at f120, after AAC.

## The Three.js test

6 s (later 7.3 s), 1080×1920, 30 fps, built from `assets/stage.js` and
`index.html`. Three books fall at 1.0, 1.6 and 2.2 s, each landing with a
ring, sparks, a flash and a hit. A 5-frame whip goes to a close-up, the
second book lights up at 3.15 s, and the stack pulls back and becomes HTML
bars at 4.5 s that fly into a list. The sound track is `sfx-synth.py slam`
at those three times plus a band-noise whoosh. The words are typed times,
not a voice.

- **Cache.** The first run stopped: "~/.cache can be changed by another user
  account" (mode 775). `HYPERFRAMES_CACHE_DIR=~/.hyperframes/cache` (mode
  700), with the existing headless shell copied in, ran.
- **Fonts.** The compiler fetched Inter (11 faces) and EB Garamond (7 faces)
  from Google Fonts; `Georgia, serif` in the CSS was drawn in EB Garamond.
  The canvas texture had used the system's serif.
- **Motion blur.** These arms used sub-frame averaging in the draw, with the
  sample count sized by projected travel (1 when under 1.5 px; otherwise one
  per 2 px, 16 to 64).

  | Arm | Frame 84, mid-whip |
  |---|---|
  | samples fixed at 1 | sharp |
  | 8 | stepped copies |
  | sized | a smooth streak |

  Render time with `--workers 4`, as the CLI printed: 11.3 and 16.5 s
  without blur, 20.8 and 18.5 s sized. Without `--workers`, the CLI chose 2
  to 6 workers per run, and times ranged from 26.5 to 100.2 s, so those runs
  measure nothing about blur.
- **Repeat renders** were not bit-identical:

  | Compared | Frames identical | Worst PSNR |
  |---|---|---|
  | two sized renders | 141 of 180 | 50.12 dB (frames 69–76) |
  | the copy in `references/` against the test | 117 of 180 | 50.14 dB |
  | two renders of the final 7.3 s copy | 198 of 219 | 55.29 dB |

  Audio was identical.
- **Impacts.** The mix put each hit on its landing frame (30, 48, 66), and
  `breakdown.py` read the hits at −1, 0 and 0 frames.
- **3D to HTML**, in order of the renders:

  | Render | Change | Result |
  |---|---|---|
  | 1 | 2-frame cross-fade, CSS `Georgia` | letters doubled at frame 136; the 3D-only glow vanished at the swap |
  | 2 | same font loaded before drawing the textures, books squared to the camera, glow off before the swap, swap on one frame, bar colour read on the swap frame | bars black on every frame: only the worker that drew the swap frame read the colour |
  | 3 | colour read in setup from a render of the swap time | still black: the read point was left of the canvas, as the spine is wider than the frame |
  | 4 | read point kept inside the canvas | colours matched; no doubled letters |

  In render 4 the swap still changed the stack's band (y 600–1400) by 18.13,
  mean absolute grey difference. Ordinary consecutive pairs in that band
  changed by 3.01 (f100 to 101), 5.27 (f140 to 141) and 4.36 (f150 to 151).
  The text sat about 10 px apart vertically.
- **`check --json`** on the copy: ok, no errors. It first warned
  `outside_safe_zone` for the counter and the caption; they were moved into
  the narrowest of HyperFrames' Shorts, Reels and TikTok areas. Still
  warned:
  - `canvas_content_at_edge`;
  - `line_unread`: the one-word spine labels are on screen 0.17 s at the
    swap, carrying on the 3D labels;
  - `nested_structure_needs_subcomposition`.

  Final render of the copy: sha256 `10083dae…0d91a` (not in this repo:
  historical).

**Not measured.** A real voice with aligned word times. A piece longer than
7.3 s. Chrome's software GPU (`--no-browser-gpu`). Page motion blur on the
HTML text. Remotion. Whether the ad was in fact made with Three.js or
HyperFrames.
