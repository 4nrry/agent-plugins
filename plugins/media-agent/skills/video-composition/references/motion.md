# Motion for short vertical video

Cut accents, kinetic text and their sounds. The first part comes from one
series (2026-10) at 30 fps and 1080×1920, drawn per frame in
numpy and PIL over 540×960 plates. Every effect is a function of the frame
number, with no random state, so a re-render gives the same frames.

## Contents
- Proven in production
- Next techniques
- Tools

## Proven in production

### Punch-in on the cut

The incoming plate starts zoomed and settles:

`z(t) = 1 + push·(t − t0)/shot + 0.12·e^(−(t − t0)/0.08) + bump·e^(−(t − beat)/0.16)`

| Term | Value |
|---|---|
| Punch at the cut | scale 1.12, back to about 1.03 after 3 frames (tau 0.08 s) |
| Slow push across the shot | +0.04 by its last frame |
| Bump when a headline lands | +0.09, tau 0.16 s |

Crop the centre `w/z × h/z` and scale it back up; skip when `z ≤ 1.0005`.

### Whip transition

Six frames, three either side of the cut. The plate slides horizontally by a
fraction of its width:

| Frame from cut | −3 | −2 | −1 | 0 | +1 | +2 |
|---|---|---|---|---|---|---|
| Offset | −0.08 | −0.22 | −0.45 | +0.45 | +0.20 | +0.07 |

- Smear along the move: average three copies shifted by 0.55, 0.8 and 1.0 of
  the offset.
- A whip cut replaces the static burst on that cut ([lofi-look.md](lofi-look.md));
  never both.
- Sound: a whoosh, band noise 700–4200 Hz under a `sin²` envelope, 0.22 s,
  starting 0.12 s before the cut, about −20 dBFS peak.

### Word-by-word text

- One more word every 0.14 s. Measure the whole line against the safe zone
  from the first word, so the last word cannot spill.
- Under a voice with word times (`audio` skill), each word can enter on the
  frame where it is spoken instead. Not yet used in this series; in a 25 s ad
  broken down frame by frame, each of 18 title words appeared within 2 frames
  of its spoken start.
- Each new word jolts the line ±6 px horizontally for 2 frames.
- A tick under each word: band noise 1.8–5.2 kHz, 40 ms, exponential decay,
  about −21 dBFS.

### Slam text

A headline hits 3 frames after its start time:

| Step | Value |
|---|---|
| Size | ×1.4 on the hit frame, −0.1 per frame, ×1.0 from frame 4 |
| Edge cap | growth limited to `(920 − x) / line width` (920 px of 1080), so a long line grows less and never crosses the right edge |
| Jolt | ±6 px horizontally for 8 frames |
| Layout check | at the final size only |
| Screen shake | the whole frame, 8 frames, 14 px decaying linearly to 0 |
| Flash | white at 0.45 on the hit frame, 0.18 on the next; none when the hit falls on frames 0–6, the opening the feed shows |

A deterministic shake: at frame `k` after the hit, `a = 14·(1 − k/8)`,
`dx = a·((7k mod 5) − 2)/2`, `dy = a·((5k mod 3) − 1)`.

Impact sound, 0.5 s, peak −12 dBFS:

- a low drop, a sine sweeping `38 + 80·e^(−9t)` Hz (118 to 38 Hz), decay
  `e^(−6t)`;
- a 160 Hz body at half level, decay `e^(−22t)`: phone speakers do not play
  the drop;
- a crack of band noise 1.2–7 kHz at 0.7, decay `e^(−70t)`.

The `audio` skill's `scripts/sfx-synth.py slam` is a similar impact, and its
`static` and `tick` cover the other cut sounds. The whoosh is not bundled: the
recipe above is all there is of it.

### Rules that came from review

- **A headline lands once.** When a line stays on screen across later cuts,
  only its first shot slams it or reveals it word by word; the later shots
  draw it whole and still. Without this it slammed again on every cut.
- **Trim, do not drop.** A sound whose start falls before t = 0 (a headline
  already landing on frame 0) is cut at 0 and keeps its tail, so the
  opening hit still sounds.

## Next techniques

Parameters as their sources give them; not yet tried in this series.

- **Speed ramps:** two or three per short at most, only where they add
  impact
  ([OpusClip](https://www.opus.pro/blog/best-speed-ramp-pace-control-tools-short-form)).
  In a frame-driven compositor a ramp is a remap of the source frame index.
- **Whip pan, editor style:** overlap the two clips by 10 frames, keyframe X
  position so one leaves as the other enters, add directional blur on X, then
  Levels to lift the darkened edges
  ([PremiumBeat](https://www.premiumbeat.com/blog/create-whip-pan-using-built-effects-premiere-pro/)).
  The 6-frame whip above is the shorter version.
- **Stutter cuts:** slice a clip and delete some pieces, mixing 2-frame and
  5-frame slices so the rhythm is irregular
  ([PremiumBeat](https://www.premiumbeat.com/blog/glitch-effect-premiere-pro/)).
- **RGB split:** three copies, one per channel, offset slightly, with
  `wiggle(5,10)` on each position
  ([AEJuice](https://aejuice.com/blog/how-to-do-rgb-split-in-after-effects/)).
  In After Effects `wiggle(5,10)` means 5 changes a second of up to 10 px.
  The tape look's chroma shift is the static version.
- **Hormozi captions:** a heavy sans-serif (The Bold Font, Montserrat Black), word by word, 3–5 key phrases
  in yellow or green, white text with a 10–15 pt black stroke, and the
  highlight in sync with the speech
  ([Fluxnote](https://fluxnote.io/guides/how-to-make-alex-hormozi-style-captions)).
  This conflicts with the skill's rule of one emphasis at a time; pick one
  per series.
- **On a Three.js stage:** a camera whip with sub-frame motion blur, an
  impact (flash, ring, sparks, number and hit on one frame) and the hand-off
  from 3D to HTML, measured in a 6 s test: [threejs.md](threejs.md).
- **Documentary map moves:** track points placed in Google Earth Studio,
  exported as 3D data to After Effects, where a script builds a 3D camera and
  null layers with text attached, so labels follow the camera
  ([PremiumBeat](https://www.premiumbeat.com/blog/making-maps-for-johnny-harris/)).
- **Short-form B-roll, split layouts and tactile foley** (measured across 27 top
  Instagram Reels in [`nateherkai/herk-edit-kit`](https://github.com/nateherkai/herk-edit-kit),
  MIT, and [`lemomo-ai/lemo-opuscar`](https://github.com/lemomo-ai/lemo-opuscar)):
  - **Three vertical layouts (1080×1920, hard cuts):** **Split** (`y 0..880`
    top B-roll/card, speaker or character below) for 30–42% of the reel,
    opening Frame 0 on a split with the topic's visual on top; **Full B-roll**
    for 50–55% (one moving visual per spoken noun phrase; never shrink a full
    web page to phone size — crop to the phrase/element so it fills the panel);
    **Punch-in** (`5–15%`) on the speaker for pivots, emphasis and the CTA.
    The speaker stays on screen ~45% of the reel and is never gone longer than
    ~3.5 s.
  - **Phrase-boundary cutting:** speech starts within `0.1 s`; cut dead air
    between phrases (`< 0.2 s`), never inside a breath group, and keep natural
    comma beats (`0.2–0.4 s`).
  - **Camera variety and 3-beat acting:** at least 4 distinct camera moves or
    framings per short, staging foreground, midground and background; character
    actions follow *anticipation → action → contact freeze / follow-through*.
  - **Sound layers and silences:** three layers (ambience, tactile foley — soft
    taps, dry clicks, paper, cloth, air rather than laser zaps — and ducked
    music), J-cut / L-cut audio transitions across visual cuts, and 1–2 brief
    silences before the turn or emotional peak.

## Tools

Stars and licences checked with `gh api repos/<owner>/<repo>` on 2026-10-30,
2026-11-11 and 2026-11-22.

| Tool | What it does | Licence, stars |
|---|---|---|
| [HyperFrames](https://github.com/heygen-com/hyperframes) | HTML, CSS and seekable animation (GSAP, Lottie, Three.js) to deterministic MP4; how to run it is in [hyperframes.md](hyperframes.md) | Apache-2.0, ~82.9k |
| [Hypit](https://github.com/hypit-ai/hypit) (fork [`4nrry/hypit`](https://github.com/4nrry/hypit)) | viral-video cloning workflow (`SVML` / `SVS` / `SVRun`), star image dependency graphs, word-anchored semantic timing and depth-stack cards; **licence trap:** internal/client production and forking allowed, multi-tenant SaaS or commercial redistribution of its code prohibited | Apache-2.0 with conditions, ~31.0k |
| [Remotion agent skills](https://github.com/remotion-dev/skills) | Remotion best practices as agent skills (`npx remotion skills add`) | no licence file in the repo; Remotion's own licence in [remotion.md](remotion.md), ~7.7k |
| [rea-video](https://github.com/JuneYaooo/rea-video) (fork [`4nrry/rea-video`](https://github.com/4nrry/rea-video)) | shot-by-shot video reverse engineering (live, AI, 3D, stop-motion, code) into `VIDEO.md`: camera moves, drawn layers, overlays, sound events and remake plan | Apache-2.0, ~11.9k |
| [OpenMotion](https://github.com/nexu-io/openmotion) (fork [`4nrry/openmotion`](https://github.com/4nrry/openmotion)) | agentic motion-graphics studio and reference-video remake workflow over HyperFrames and Remotion | Apache-2.0, ~14.8k |
| [pixelfx](https://github.com/patch-gg/pixelfx) (fork [`4nrry/pixelfx`](https://github.com/4nrry/pixelfx)) | 244 procedural pixel-art VFX and 12 acted moves in two buffers (`color` + additive `light`), contact-sheet loop and Aseprite `--sheet` export (`cutout-animation` skill) | MIT, ~8.7k |
| [anymove](https://github.com/patch-gg/anymove) (fork [`4nrry/anymove`](https://github.com/4nrry/anymove)) | two-view AI video motion capture triangulated onto a 3D rig in Blender 5.x, `.glb` out (`3d-scenes` skill) | Apache-2.0, ~0.7k |
| [herk-edit-kit](https://github.com/nateherkai/herk-edit-kit) (fork [`4nrry/herk-edit-kit`](https://github.com/4nrry/herk-edit-kit)) | 15 short-form editing skills for HyperFrames/GSAP, 406 motion-graphics cards and measured Reel layout/pacing playbook (AIS brand assets excluded from MIT) | MIT (code/skills), ~3.1k |
| [ffmpeg-skill](https://github.com/kajisho5/ffmpeg-skill) | 42 local FFmpeg operations with machine-readable contracts, self-verification and MCP server | MIT, ~9.4k |
| [animate](https://github.com/cth9191/animate) (fork [`4nrry/animate`](https://github.com/4nrry/animate)) | procedural single-canvas animation in pluggable styles (cut paper, crosshatch, riso, sketchbook, isometric) with beat-grid and loudness checks | MIT, ~2.2k |
| [claude-code-video-toolkit](https://github.com/digitalsamba/claude-code-video-toolkit) | end-to-end script, voiceover, music, Blender 3D / Remotion composition and render toolkit | MIT, ~2.7k |
| [godogen](https://github.com/htdt/godogen) | skills for Godot, Bevy, Babylon.js and Three.js headless video capture plus local GPU asset generation | MIT, ~7.4k |
| [EffectCraft](https://github.com/storytold/effectcraft) & [FilmCraft](https://github.com/storytold/filmcraft) | open-source motion-graphics compositor (308 effects, 3D camera, MCP) and nonlinear editor in pure Rust | MIT / Apache-2.0, ~9.1k & ~18.8k |
| [Awesome Opus 5.5 Videos](https://github.com/yihui-dev/awesome-opus5-5-videos) | 703 prompts extracted from viral code-rendered videos (Canvas, Three.js, SVG, GSAP) | MIT, ~16.1k |
| [Lemo-Opuscar](https://github.com/lemomo-ai/lemo-opuscar) & [lemo-animi](https://github.com/lemomo-ai/lemo-animi) | 99 code-drawn film styles and 8 stop-motion puppet styles; **licence trap:** code is MIT, but docs/styles are `CC BY-NC 4.0` with permission to make your own commercial films, **not** to redistribute or sell the docs inside a product | MIT code / CC BY-NC 4.0 docs, ~19.6k & ~0.2k |
| [LottieFiles motion-design-skill](https://github.com/LottieFiles/motion-design-skill) | timing, easing and choreography rules for UI motion, any animation system | MIT, ~2.6k |
| [Lottie Creator MCP](https://docs.lottiefiles.com/en/creator/13_ai-tools/lottie-creator-mcp) | a local bridge that lets an agent build and edit animations in Creator; needs Node 18+ and a Creator tab open | LottieFiles service |
| [Rive CLI](https://rive.app/docs/cli/overview) | an agent writes the scene as [RML](https://rive.app/docs/runtimes/advanced-topic/rml) (XML `.rml` files); the CLI compiles to `.riv`, previews and captures frames headless | Rive service |
| [OpenMontage](https://github.com/calesthio/OpenMontage) | an agentic video production system: pipelines, tools and skill files | AGPL-3.0, ~73.2k |
| [Revideo](https://github.com/midrender/revideo) | TypeScript scenes rendered to video with a headless API (moved from `redotvideo/revideo`; last push 2026-07-15) | MIT, ~4.2k |

**AGPL-3.0 (OpenMontage).** Running it to make videos does not put the
videos under the AGPL: output is covered only where substantial parts of it
are copied from the program's own text
([GPL FAQ](https://www.gnu.org/licenses/gpl-faq.html#GPLOutput)). Distributing
a tool that contains its code obliges you to offer that tool's source under
the AGPL, as with the GPL; so does running a modified copy that other people
use over a network
([AGPL-3.0, section 13](https://www.gnu.org/licenses/agpl-3.0.html#section13)).
Read its ideas; do not paste its code into a closed project.
