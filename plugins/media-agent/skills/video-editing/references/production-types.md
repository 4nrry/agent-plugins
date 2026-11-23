# How a reference video was made, and how to remake it

Before you remake a reference video, decide how each shot was made. A filmed
shot, an AI clip, a 3D render and a code animation each need a different
remake, and the wrong guess costs a whole generation budget.

Source: [`4nrry/rea-video`](https://github.com/4nrry/rea-video) (fork of
`JuneYaooo/rea-video`), Apache-2.0, read at commit
`99033f7ec8e2ddd51da40259d99d679897860c95` (2026-11-23). Files read:
`skills/rea-video/references/taxonomy.md`, `docs/en/what-it-detects.md`,
`rea_video/classify.py`, `rea_video/capabilities/` (`routing.yaml`,
`MATRIX.md`, `README.md`) and `eval/RESULTS.md`. Paraphrased, not copied. The
repo's own text is mostly Chinese. **Not yet run here:** nothing from this
repo was installed or run, so every threshold and accuracy below is the
repo's claim, not a measurement of ours.

## Contents

- [Where this fits next to breakdown.py](#where-this-fits-next-to-breakdownpy)
- [The 11 production types](#the-11-production-types)
- [Overlays and AI edits on top](#overlays-and-ai-edits-on-top)
- [Look-alike pairs to check by eye](#look-alike-pairs-to-check-by-eye)
- [From type to remake: the routing matrix](#from-type-to-remake-the-routing-matrix)
- [What to trust](#what-to-trust)

## Where this fits next to breakdown.py

The two answer different questions.

| | `scripts/breakdown.py` (this plugin) | rea-video |
|---|---|---|
| Asks | When does it change: cuts, flashes, stalled tiles, sound hits, word frames | What made the picture: filmed, AI, 3D, code |
| Output | Timing, to the frame | A label per shot, with the evidence, and a remake route |
| Needs | ffmpeg, numpy, Pillow | Python 3.10+, ffmpeg, OCR models; an optional vision model |
| Runs here | Yes, with a self-test | No |

Use `breakdown.py` first: it gives the cut list and the beat table. Then label
each shot with the table below, by hand, reading the contact sheets it wrote.
You do not need to install rea-video to use its taxonomy; the evidence
column is written so a person or an agent can check it on the frames. If you
do want the tool, its `decompose` command writes `breakdown.json` and a
report; that is untested here.

## The 11 production types

"Measurable" means the repo decides it from pixels, frame rate and sound with
no vision model. The three marked "look" cannot be measured: someone has to
look at the frames.

| Type | Measurable evidence | Remake route |
|---|---|---|
| Live action | Sensor noise above sigma 1, temporal noise above 0.8, fewer than 55% of pixels unchanged frame to frame, handheld shake, native 60 fps, camera metadata | Real footage, or image-to-video as an approximation |
| AI-generated video | Photographic texture with no sensor noise, repeated or interpolated frames on a 24 to 30 fps cycle, floating camera; by eye: bad hands, text, warping, flicker | First and last frame generation |
| Digital avatar | Fixed camera, frontal face, only mouth and head move, audio-driven | TTS or a cloned voice, then an avatar model |
| 3D render | Flat or clean materials, background not frozen, stable geometry with no warping | Blender or similar, or first and last frame as an approximation |
| Code or template render | More than 20% flat blocks, fewer than 70 colours, many straight edges, background frozen while parts move, no material texture (smooth gradients, saturated fills, glow, shader fields), or bright specks and thin lines on black (particles, wireframes) | Rebuild in Remotion or HTML; particles in Three.js, colour fields in GLSL, gradients in CSS, charts in SVG |
| Screen recording | Large light interface, dense small text, low saturation, whole-page scroll | The real screen, recorded |
| Still with pan and zoom | Whole frame fits one rigid transform for over 95% of points, residual under 0.3 px, nothing left after compensation, no 24 fps cadence | One image and ffmpeg with the measured parameters |
| Held frame | Over 85% of frames repeat pixel for pixel | One image |
| 2D animation (look) | Stable lines and flat fills, a character with a skeleton or frame-by-frame acting, often "on twos" | Character sheet then first and last frame; for exact lip sync, build in After Effects, Live2D or Spine |
| Stop-motion (look) | Real material (clay, felt, paper), jerky motion, slight flicker between frames, constant light on one object | Best: shoot it, fixed camera, about 12 frames per second. AI only approximates |
| Film or TV footage (look) | Hints only: picture inside black bars, a 24 or 25 fps source. By eye: a known actor or show, crew-level lighting, coverage from several angles, crowds and full sets, a channel logo | Find the original clip and cut it (the rights belong to the studio); else reshoot the same framing and light |

Rules that decide the hard cases:

- "Live action" means footage the video's own author or client shot. Footage
  cut from an existing film, series or short drama is "film footage", however
  real it looks.
- A rendered card that holds still is "code render", not "held frame".
- A game being played is "screen recording" (look for the HUD: health bar,
  minimap, crosshair). A game cinematic with no HUD is "3D render".
- A graphic novel with only pan and zoom is "still with pan and zoom". Add
  blinks and hair moving and it is "2D animation". Lines that swim between
  frames make it "AI-generated".
- The 24 to 30 fps repeat pattern (about 20% of frames repeated, period 4 to
  6) says the source ran at 24 fps: AI, 3D, or film. It is not a phone.
- Native 48 fps or more with no repeats and no interpolation cycle usually
  means a phone or camera.
- A platform re-encode removes the noise evidence. Then trust frame rate and
  the absence of repeats, not "no noise".
- Sharpness that rises and falls on a cycle, with no repeated frames, is weak
  evidence of interpolation. Re-compression produces it too.

## Overlays and AI edits on top

Each shot also carries separate marks.

- **Overlays:** subtitles, styled text, titles, stickers, layout templates.
  Text on objects (a sign, a label) is kept apart from subtitles. The repo
  reads subtitles by OCR at 2 frames per second, then aligns their start and
  end to about 0.1 s.
- **Real assets** that a remake needs as files: embedded screen recordings,
  screenshots, photos, clips.
- **AI edits on filmed footage** (decided by eye): face swap, lip sync,
  restyle, outfit swap, background replacement, object add or remove,
  beauty filter. The remake plan then says "shoot first, then apply this
  edit".

| AI edit | Look for |
|---|---|
| Face swap | Flicker at the face edge and hairline; face and neck differ in tone or light; features drift in profile |
| Lip sync | Jaw does not follow; blurred teeth; only the mouth area has a different sharpness |
| Restyle | Human motion in an anime, oil or clay look; texture crawls between frames |
| Outfit swap | Cloth texture flickers; the join at the arm is soft |
| Background replacement | Halo or jagged hair edge; light direction differs between person and background; wrong perspective |
| Beauty filter | Over-smooth skin; straight background lines bend near the face |

## Look-alike pairs to check by eye

- **Filmed or AI.** Filmed: grain changes per frame, hands and distant text
  are right, cloth and liquid obey physics. AI: skin and light too perfect,
  background faces or text garbled, edges that "boil", slow floating motion,
  a freeze at the end. The measured layer is weakest on this pair, so look at
  the frames.
- **Cartoon-style AI or real 3D.** Real 3D keeps geometry and material the
  same frame to frame and loops exactly. AI drifts slightly inside a shot.
- **Particle graphics.** Glowing dots or lines on black that form an organ,
  a globe or a molecule, with no continuous shading, are code render, not 3D,
  AI or a night shot. Describe in the notes what the particles form, how they
  move and where the labels sit; "particle background" alone remakes as a
  blob of light.
- **Code gradients or 3D.** A frame with almost no fine texture (smooth
  gradient, flat colour, glow, shader field) is code, even when the whole
  frame moves. 3D shows cloth, wood or metal grain and cast shadows.
- **Code render or screen capture.** Code: large type, brand colours, crisp
  vectors, animated entrances. Capture: light ground, dense small text,
  buttons and icons, scaled or scrolled.
- **Still with zoom or an AI push-in.** An editor renders every frame
  different, with no 24 to 30 repeat. An AI push-in repeats frames and shows
  small life (breathing, blinking).
- **Stop-motion, AI imitation or filmed.** Stop-motion moves one real
  object, with fingerprints and rough edges. AI imitation drifts the texture
  of the clay itself and has no real stutter. The measured layer often calls
  stop-motion "AI" because the frame cadence looks alike.
- **Film clip, AI short drama or own footage.** A film clip has a known cast,
  crew-scale light and sets, readable text in the scene, often a logo or
  bars. AI drama has faces too perfect and too alike, wrong hands, teeth and
  text, blurred background people and mostly 5 to 10 s single close-ups. A
  disclaimer such as "for effect" is not evidence by itself.

Cuts, from the same source: a hard cut is a spike in histogram distance and
pixel difference over more than 25% of the frame area; a flash that fades
back is not a cut; a cross-dissolve has middle frames that are a linear mix
of both ends; a whip, zoom, spin, blur or shake counts only around a hard cut
(without one it is a camera move). This agrees with the cut-versus-flash
rule in `breakdown.py`.

## From type to remake: the routing matrix

`rea_video/capabilities/` is a data set of three layers: shot signals, then
**primitives** (a capability with no vendor name, 43 of them), then models
that offer a primitive. A rule names primitives, so it survives a model
swap. Each model entry has a status, access, limits, cost, licence and a
`verified` basis, ranked `probe` (own test), `user`, `vendor`, `third-party`,
`knowledge`. Entries older than 90 days count as stale. Its checker is
`scripts/validate_capabilities.py`.

The routes, with the first models it prefers (as of its entries dated
2026-10-29 to 2026-11-22):

| Shot signal | Route | First choices |
|---|---|---|
| Text, UI, charts, motion graphics | Code graphics | Remotion, HTML with GSAP and Playwright, Motion Canvas |
| Software demo | Web capture, then code graphics | HTML and Playwright, Remotion |
| Frontal talking head | Voice clone, then audio-driven avatar | MiniMax Speech 2.8, OmniHuman 2.0, Kling Avatar v2 |
| Exact motion (dance, gesture on the beat) | Motion transfer or reference video; depth or pose video as the driver | Kling Motion Control, Seedance 2.5, Wan Animate; Blender for a new camera |
| Garment change | Try-on image first, then animate it | FASHN, Kling Virtual Try-On 3, then Seedance or Kling |
| Real text on objects | Image model with text, then image-to-video | GPT Image 2.5, Qwen Image 3.0 Pro, Seedream 5.5 |
| Product that must look exact | Multi-reference image edit, then image-to-video | GPT Image 2.5, Nano Banana 2.1, then Seedance 2.5 |
| Product turning | Image to 3D, render, optional reference video | Hunyuan 3D, Rodin Gen-2.5, Blender |
| Hard camera move | Keyframes, or first and last frame | Kling 4.0, Veo 3.1, Runway Gen-4.5 |
| Lens look | Camera control | PixVerse V6, Kling 4.0, Runway Gen-4.5 |
| Same character across shots | Multi-reference, multi-shot | Seedance 2.5, Kling 3.0 or O3, Vidu Q3 |
| Own footage to edit | Video-to-video edit | Kling O3, Runway Aleph 2 |
| Re-dub only | Lip-sync redub | Sync 3, sync react-1 |
| Ambient b-roll | Text-to-video, cheapest first | MiniMax H3, Hailuo 2.3, Wan 2.2 |
| Still with pan and zoom, held frame | One image plus ffmpeg | GPT Image 2.5, Seedream, ffmpeg |
| 2D animation | Character image, then first and last frame | Kling 3.0, Seedance 2.5, Vidu Q3 |
| Stop-motion | Shoot it; AI approximates | Kling 3.0, Seedance 2.5 (prompt "stop-motion, 12 fps") |
| Film footage | Cut the original, or reshoot | ffmpeg |
| Dialogue tied to a non-frontal shot | Native-audio video model with references | Seedance 2.5, Kling 3.0, Veo 3.1 |

Audio and post routes:

| Need | Route |
|---|---|
| Narration | Word-aligned speech recognition, then clone or TTS. Chinese: MiniMax clone; English emotion: ElevenLabs |
| New voice inside the old time window | Duration-controlled TTS (IndexTTS2) |
| Music | Separate stems and read tempo, then generate new music of similar tempo and mood; do not reuse the original |
| Sound effects | Video-to-foley (HunyuanVideo-Foley; its licence excludes the EU, UK and Korea) or text-to-SFX. MMAudio weights are not for commercial use |
| Lip mismatch after generation | Lip-sync redub |
| Draft below delivery size | Upscale (SeedVR2, FlashVSR, Topaz). It advises against Real-ESRGAN on generated video (block artefacts) |
| Too few frames or slow motion | Frame interpolation (RIFE) |

Planning rules in the same file that are worth keeping:

- Text, UI and subtitles go in a code layer, never the generator, which
  redraws text wrongly. Put the picture under it and composite last.
- Merge consecutive shots of one character and scene into one multi-shot
  generation when they fit the model's length limit.
- A generation unit holds at most about 8 s of consecutive hard cuts (over
  10 s often fails). Cut a long shot at a pause and start the next from the
  last frame of the previous.
- Cut occluded transitions and outfit changes into their own units and pin
  both ends with first and last frames.
- Write each unit's prompt as the action plus its end state. Label each
  input by role. Avoid metaphors, which get drawn literally. Leave exact
  counts (fingers) to captions.
- Estimate cost per unit (seconds times price) and confirm it before
  generating. Make stills first, then a 480p or 720p draft, then upscale.
- Model entries that cannot take first and last frames together with
  reference images are marked `exclusive_inputs`; pick one mode per unit.
- Two modes, mixable per layer: **fidelity** (match structure, rhythm,
  camera, text) and **adapt** (keep why it works, rewrite the content).

## What to trust

- Its evaluation says 98 to 99.6% shot-time accuracy over 8 categories with
  no vision model, on 31 videos. The sets are split by source clip, not by
  production, and the rules were tuned on them, so read it as "close
  samples", not as a general rate. The first pass on a fresh set scored lower
  (75.6% on the real-asset check). Not reproduced here.
- Sound effects are its weak spot: precision was about 0.2 on a mixed track.
  Music source (AI or library) was right in 2 of 5.
- The model names, prices and limits are dated snapshots, many from
  third-party summaries (medium or low confidence). Treat them as leads and
  re-check before you spend. The matrix goes stale in weeks.
- Release names in it (Seedance 2.5, Kling 4.0, and so on) are as the repo
  gives them; none was checked here.
