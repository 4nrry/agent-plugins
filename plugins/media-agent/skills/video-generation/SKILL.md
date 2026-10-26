---
name: video-generation
description: Generates short video shots with any video model — animate a chosen still, one camera move, resolution by use, check every clip. Use for generated video, b-roll, an animated photo, a drone shot, image-to-video or text-to-video, or when a video model is named (Veo, Grok Imagine, Sora, Kling).
---

# Video generation

The rules below hold for any video model. How to run each tool, its
resolutions and its quirks are in [references/tools.md](references/tools.md).

## Start from a still

Text-to-video picks its own framing. Starting from a still keeps the
composition and only moves the camera, so make and choose the still first
(`image-generation` skill), then animate it. From this skill's directory, the
pattern on a subscription (Grok Build), which bills no API key:

```bash
scripts/grok-video.sh "slow drone push forward along the windrows, mist drifting, no text" shot.mp4 --image still.png --res 720p
scripts/contact-sheet.sh check.jpg still.png shot.mp4
```

`scripts/omni.py` takes the same prompt and still on the Gemini API key, which
bills every call; [references/tools.md](references/tools.md) marks what each
route bills.

When the shot must land on an exact frame (a match cut, a loop back to the
opening, room left for the product composite), give the last frame too where
the model takes one (`omni.py --last end.png`), and describe the move between
them.

## A subject across shots

- Pass the subject's reference images where the model takes them
  (`omni.py --ref`, repeatable; the sheet from the `image-generation` skill)
  and name the subject in the prompt.
- To continue a shot, extend the clip rather than generating a new one: the
  model keeps the subject, the motion and the sound.
- To fix one thing in a clip, edit it ("change only the sky") where the model
  edits video; a new generation changes everything else too.

## Prompts

- Describe the motion only; the still already holds the scene.
- One camera move per shot, with its framing: "medium shot, slow push
  forward".
- Sound on its own line ("Audio: light wind, distant birds"). Write dialogue
  after a colon, not in quotes, which some models render as on-screen text.
- Write in English, and keep text out of the frame. Where the model has no
  negative prompt, say "no text, no people" in the prompt itself.

## Resolution and cost

- Pick the resolution by how the shot is shown: full screen needs native 1080p;
  a blurred background, a small card or a Reels backdrop is fine at 480–720p.
- Generate at the resolution you need, or let the vendor upscale it. Do not
  upscale a low-resolution clip yourself frame by frame: it takes tens of
  minutes per clip and invents detail.
- Draft with the cheap model, then run the same prompt on the premium one. The
  premium model can reinvent the geometry: compare it with the draft.

## Check before the timeline

- Watch every clip in full. Errors appear mid-clip, not on the first frame:
  hands, any text on screen, lip sync, and clothes or props that change
  between shots. Regenerate a failed shot; do not ship the almost.
- `scripts/contact-sheet.sh` puts 4 frames of each video on one sheet beside
  the still.

## Fitting it into the piece

- Generated shots are short (2–4 s) and supporting: atmosphere around real
  footage, never in place of the proof (product, dashboard, report).
- Give generated and real footage the same color treatment and the same
  grain: generated footage reads as too smooth beside real footage.
- A blurred low-resolution clip (`filter: blur(6px) brightness(.6)`) can sit
  behind Reels typography.
- Never generate the product, logos or real people (`image-generation` skill).
- Generated video carries provenance (watermarks such as SynthID, C2PA
  metadata), from which platforms add an AI label. A realistic generated shot
  is declared at upload as AI-made: Meta, TikTok and YouTube require it of whoever posts,
  whatever the metadata says (`video-composition` skill,
  `references/short-form.md`).
