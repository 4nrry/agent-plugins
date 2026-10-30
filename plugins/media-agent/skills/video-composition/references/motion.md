# Motion for short vertical video

Cut accents, kinetic text and their sounds. The first part comes from one
series (Sinal Público, 2026-10) at 30 fps and 1080×1920, drawn per frame in
numpy and PIL over 540×960 plates. Every effect is a function of the frame
number, with no random state, so a re-render gives the same frames.

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
`static` and `tick` cover the other cut sounds.

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
  `wiggle(5,10)` on each position (After Effects: 5 changes a second, up to
  10 px)
  ([AEJuice](https://aejuice.com/blog/how-to-do-rgb-split-in-after-effects/)).
  The tape look's chroma shift is the static version.
- **Hormozi captions:** a bold condensed font, word by word, 3–5 key phrases
  in yellow or green, white text with a 10–15 pt black stroke, and the
  highlight in sync with the speech
  ([Fluxnote](https://fluxnote.io/guides/how-to-make-alex-hormozi-style-captions)).
  This conflicts with the skill's rule of one emphasis at a time; pick one
  per series.
- **Documentary map moves:** track points placed in Google Earth Studio,
  exported as 3D data to After Effects, where a script builds a 3D camera and
  null layers with text attached, so labels follow the camera
  ([PremiumBeat](https://www.premiumbeat.com/blog/making-maps-for-johnny-harris/)).

## Tools

Stars and licences checked with `gh api repos/<owner>/<repo>` on 2026-10-30.

| Tool | What it does | Licence, stars |
|---|---|---|
| [HyperFrames](https://github.com/heygen-com/hyperframes) | HTML, CSS and seekable animation (GSAP, Lottie, Three.js) to deterministic MP4; agent skills included | Apache-2.0, ~75.7k |
| [Remotion agent skills](https://github.com/remotion-dev/skills) | Remotion best practices as agent skills (`npx skills add remotion-dev/skills`) | no licence file in the repo; Remotion's own licence in [remotion.md](remotion.md), ~5.9k |
| [LottieFiles motion-design-skill](https://github.com/LottieFiles/motion-design-skill) | timing, easing and choreography rules for UI motion, any animation system | MIT, ~2.6k |
| [Lottie Creator MCP](https://docs.lottiefiles.com/en/creator/13_ai-tools/lottie-creator-mcp) | a local bridge that lets an agent build and edit animations in Creator; needs Node 18+ and a Creator tab open | LottieFiles service |
| [Rive CLI](https://rive.app/docs/cli/overview) | an agent writes the scene as [RML](https://rive.app/docs/runtimes/advanced-topic/rml) (XML `.rml` files); the CLI compiles to `.riv`, previews and captures frames headless | Rive service |
| [OpenMontage](https://github.com/calesthio/OpenMontage) | an agentic video production system: pipelines, tools and skill files | AGPL-3.0, ~73.2k |
| [Revideo](https://github.com/midrender/revideo) | TypeScript scenes rendered to video with a headless API (moved from `redotvideo/revideo`) | MIT, ~4.2k |

**AGPL-3.0 (OpenMontage).** Running it to make videos does not put the
videos under the AGPL: output is covered only where substantial parts of it
are copied from the program's own text
([GPL FAQ](https://www.gnu.org/licenses/gpl-faq.html#GPLOutput)). Distributing
a tool that contains its code, or running a modified copy that other people
use over a network, obliges you to offer that tool's source under the AGPL
([AGPL-3.0, section 13](https://www.gnu.org/licenses/agpl-3.0.html#section13)).
Read its ideas; do not paste its code into a closed project.
