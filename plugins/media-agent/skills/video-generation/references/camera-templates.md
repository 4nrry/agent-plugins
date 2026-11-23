# A camera engine and 137 camera-move templates

A way to fix the camera of an AI video with code. You write the move in
Three.js, render a grey clip where every person is a striped capsule (a
"pill"), and send that clip to a video model as the reference video. The
model copies the camera and the timing, and paints the people and the place
from the prompt. The idea is in
[prompting.md](prompting.md#3d-pill-pipeline-camera-control); this page is
the kit that makes the clip.

Source: [`4nrry/ai-filmmaking-camera-control-seedance-2-5`](https://github.com/4nrry/ai-filmmaking-camera-control-seedance-2-5)
(fork of `sirioberati/ai-filmmaking-camera-control-seedance-2-5`), MIT, read at
commit `602aa2348b0ae67589ce533fff571adced724811` (2026-11-07). Files read:
`README.md`, `AGENTS.md`, `NOTICE.md`, `answers/` (all five files),
`docs/engine.md`, `docs/costs.md`, `docs/known-limits.md`,
`templates/INDEX.md`, `engine/cinematic/tools/render-pill.sh` and
`engine/cinematic/package.json`. Paraphrased, not copied.

**Not yet run here:** nothing from this repo was installed, rendered or sent.
Every number below is the repo's own claim from its author's runs.

## Contents

- [What the engine is](#what-the-engine-is)
- [Render a pill clip locally](#render-a-pill-clip-locally)
- [The 137 templates, grouped](#the-137-templates-grouped)
- [What the model step proved, and what it did not](#what-the-model-step-proved-and-what-it-did-not)
- [Licences to read first](#licences-to-read-first)

## What the engine is

`engine/cinematic` is Remotion (React) driving Three.js, not Blender. Every
frame is a pure function of the time: positions, poses, physics (baked once
with Rapier) and the camera are read from tables or formulas, so frames can
render out of order on several workers and two renders match. This is the
same rule as `threejs.md` in the `video-composition` skill.

| Part | Fact |
|---|---|
| Stack | Remotion 4.0.522, three 0.170.0, React 19, Rapier 0.14.0, headless Chromium that Remotion downloads on the first render |
| Needs | Node 22.12 or newer, ffmpeg, network once |
| Frame | 24 fps; 2.39:1 picture, 1920 by 804 inside 1920 by 1080; 180-degree shutter; full-frame 36 mm sensor |
| Reference clip | Cropped to 1280 by 534, 24 fps, no audio |
| Stand-ins | A striped capsule or pin, as tall as the person, with a white dot at eye height on the side it faces. No limbs, so no body motion to copy. About 75 clips use the capsule, 62 the pin |
| Set | Coarse grey blockout. The prompt must rebuild the set in words, or the model copies the grey boxes |
| Camera support | The label you write in `rig:` picks a small deterministic float: dolly and crane are glassy, steadicam a little, drone has wind and banks, FPV shakes more, handheld most |
| Camera HUD | A measure pass reads every move back as pan, tilt, dolly, truck, boom, whip and zoom in m/s and degrees per second |
| Film paths | 33 camera moves of 3 to 8 s, distilled from a research dataset of camera tracks estimated from film clips (see licences) |

Per-shot looks other than the pill exist as flags (`--storyboard`, `--pencil`,
`--ghost`, `--plate`). In the author's six-way test of one fight, only the
striped pills gave a real alley, natural punches and the right places;
mannequins carried their robotic walk into the result, ghosts kept some of it,
and an empty set put people in the wrong places.

## Render a pill clip locally

```bash
cd engine/cinematic && npm install
tools/render-pill.sh CAM06-Orbit     # add --standin capsule for the capsule
```

It writes `.work/out/pill/<ID>.pill.mp4` (set `CAMERA_CONTROL_HOME` to move
it). Inside, it runs `node render.mjs --videos <ID> --boxes --clean
--subframes 5 --scale 0.6667`, then ffmpeg crops to 1280 by 534 at 24 fps with
no audio. `--clean` leaves the picture only, with no slate or report.

- **Keep a reference video under 29 s in total.** The earlier hosted API
  refused a clip it measured at 30.00 s.
- Never use `--marks` (a 1 m checker on every surface) for a reference: the
  model painted a chessboard.
- The shell scripts were tested on macOS by the author; `render-pill.sh` is
  plain `sh` but is untested on Linux, here or there.
- A template is one small `template.ts` plus a `sent.json`. Its folder under
  `templates/<ID>/` holds the pill clip, preview, prompts and notes. The repo
  says a new template takes about 12 lines (`docs/build-your-own-template.md`).
- The checks `tools/check.sh` (frames) and `tools/motion.sh` (motion) exit 0
  on failures unless `STRICT=1`. A motion note is not proof of a visible
  fault: look at the frames.
- The result videos are not in git. They are a release download, and the
  whole clone is about 440 MB.

This is an alternative to a Blender pill clip from the `3d-scenes` skill. Use
this when the move is the point and the set can stay grey.

## The 137 templates, grouped

The id prefix is the group. The index is `templates/INDEX.md`; each card
says what the move means on screen.

| Group | Count | What is in it | Notes |
|---|---|---|---|
| `CAM` | 48 | Camera moves: locked-off, pan, push in, pull out, dolly zoom, orbit, crane up and down, steadicam follow and lead, tracking, over-the-shoulder pair, whip pan and whip tilt, handheld, chase drone, FPV, slow zooms, tilts, pedestal, short arc, arc and rise, Dutch angle, barrel roll, run and gun, POV walk and look-around, two-shot truck, slider, rack focus, reverse dolly zoom, drone orbit, dive, reveal and rise, low follow, orbit a walker | The core set. CAM01, CAM26, CAM29, CAM30, CAM46 are locked-off and kept as studies |
| `ANG` | 36 | Shot size and lens studies: extreme wide to extreme close-up, eye level, bird's-eye, worm's-eye, profile, three-quarter, from behind, Dutch, upside-down, super wide, fisheye, peephole, security cam, long lens and telephoto, hip, knee, ground-level walk, shoulder level, over the head, symmetrical, frame within a frame, leading lines | Locked-off. Only 4 were ever sent, and 33 of the 36 clips fall under the repo's own motion threshold. Not recommended as templates; use for framing reference |
| `OBJ` | 16 | Object and vehicle moves: push in on an object, hero orbit, crane up a monument, truck past with parallax, low car tracking, top-down, rack focus, wipe reveal, through a doorway, crash zoom, height reveal, flyby pan, macro slider, fly through a window, top-down spiral, product spin | Use for products and vehicles |
| `SC` | 10 | Whole scenes: forest clearing, interior dialogue, street walk-and-talk, car interior, space flyby, rooftop chase, alley fight, heist approach, stand-off, car through a barrier | Multi-shot; people as pills |
| `ACT` | 8 | Action coverage: bullet-time orbit, Snorricam, crash zoom and whip fight, sprint dolly zoom, parkour track, hero low arc, fight coverage, fall drop | ACT07 was refused by the model's copyright filter on every try and has no result |
| `FAM` | 6 | Famous shots rebuilt from measurements of public clips: 360 booth, walk away from an explosion, trunk shot, leap of faith, Bay 360, Peter Pan flight | Only the repo's own pill blockouts and notes ship, no frames |
| `PRD` | 6 | Product commercial moves: frozen splash orbit, robot-arm snap, exploded build, probe fly-through, skyline dive, glambot | PRD01 was sent back (the pill was half hidden by the splash) |
| `ONE` | 4 | One-takes: crane to follow with a whip reveal, drone dive into a chase, interior oner, orbit then push then rack | |
| `STORY` | 2 | Longer chained pieces: dive to the shutter, the gap | STORY03 uses an `extend` call |
| `SHOW` | 1 | The Handoff: a 30 s scene of ten shots, two people, a case, a drone and a chase, planned as pills first | The long-form example |

Counts check: 48 + 36 + 16 + 10 + 8 + 6 + 6 + 4 + 2 + 1 = 137.

Of the 137, 93 have prompts and 92 have at least one result video; 64 have a
main result. The 44 never sent are mostly the locked-off ANG clips, plus
CAM31 (the pin hidden for the first second), CAM33 and CAM34 (point of view,
nobody in frame), CAM41, CAM43 and CAM44 (a tiny pin in drone shots). The
repo also says 51 sends use a re-render of the pill clip, not the exact file
that was uploaded, and five prompts are rebuilt, not the text sent.

## What the model step proved, and what it did not

The model step was shown on **Seedance 2.5 through a paid hosted service**
(Tein, tein.ai). You need your own account and key, and the engine step above
does not. The pill clip goes in as `reference_video`, the face or product
photo as `reference_image`, with a prompt that names every stand-in and says
no pill appears. Rules from its agent file: never send a request or spend
credits without a yes for that exact request, with the price shown first;
start with a 480p draft and finalize only when the draft is right.

Cost, as the repo measured on an earlier hosted API (rates differ on Tein;
read the price first): a draft bills the 480p rate and its final the 1080p
rate, so a final costs about 5.5 times its draft. With a video input the
billed seconds are input plus output, never less than 1.67 times the output.
A 7 s pill-video draft was about 1,020 credits at 1,000 credits per dollar.
Failed jobs were refunded.

The repo's `answers/` file set answers 137 questions: 86 proven by a file or
a re-measurable number, 47 proven in part, **4 UNPROVEN**. They are:

| Question | Not shown | The test it names |
|---|---|---|
| A8: how it differs from first and last frame, plain image-to-video, or a Blender previs | No baseline of any of them was run as a camera comparison | Send CAM06 through each route and measure camera path and cuts |
| Q70: mixing the pill video and a sheet of drawn frames in one request | No request ever sent both | One 30 s draft with both, compared on cut timing and look |
| Q78: the effect of prompt length | Prompts ran 384 to 3,220 words (median 992); a 1,798-word prompt was followed, a 3,000-word one paraphrased dialogue | One prompt at 800, 1,800 and 3,000 words, with speech and cut checks |
| Q92: a true 4K of an existing draft on Tein | Not tried on Tein; on the earlier API the final ignored 4K and came back at 1080p | Finalize a 4 s draft at 4K and read the size |

Other limits it states:

- The pill **video** landed 9 of 9 cuts on one film; the drawn **sheet**
  route landed 1 of 9 and 3 of 9, because a sheet has no clock. This is one
  film.
- Hold every shot and camera effect 2 s or more, and move the camera in every
  clip you send. Locked-off clips gave stiff drafts.
- A repeat run is a new take, even with the prompt restored word for word.
- Statues still came out as odd stand-in shapes in four templates.
- Speech can start 1 to 2 s early, a line can be said twice, and the checks
  measure mouth movement, not lip sync.
- The pill has no hands or feet, so those come from the prompt only.

None of this was re-run here, and the repo gives no result for any model
besides Seedance 2.5. Whether another reference-video model follows a pill
clip the same way is untested.

## Licences to read first

- Code, prompts, notes and the pill clips: MIT.
- The animated rig (Quaternius Universal Animation Library 1 and 2): CC0.
- **Remotion** is not MIT. It is free for individuals, for-profit companies
  with up to 3 employees, and non-profits; a larger for-profit company needs
  Remotion's company licence. Check this before using the engine at work.
- The 33 film camera paths come from a research dataset whose code and data
  repos are marked MIT, but whose clips are copyrighted films. Only distilled
  curves ship. Check its terms before a product.
- Some examples show a real person's face and voice, and some product shots
  carry brand marks: neither is covered by the MIT licence.
- Generated output follows the terms of the service that made it.
