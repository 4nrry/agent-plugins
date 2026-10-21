---
name: generative-media
description: Uses generative AI as a design tool in a marketing piece — explore scene directions with quick stills, pick the framing on a contact sheet, animate the chosen still into video, and fit the shot into the video or carousel without clashing with the brand. Covers which tool fits each task (Grok Build to explore, Antigravity `agy` for the final still, Veo for 1080p shots, Grok for low-resolution background clips, Nano Banana by API), how to prompt each, the still-to-video flow that controls composition, and what never to generate (the product, text, real people). Use when a task asks for a generated image, scene, generated b-roll, animating a photo, an aerial shot, a moodboard, a storyboard, Veo, Nano Banana, Grok Imagine, agy, or "generate an image/video of..." for a piece.
---

# Generative media as a design tool

Generating is the cheap step; choosing and fitting make the piece. Prerequisites:
`grok`, `agy` and `GEMINI_API_KEY` working; setup is in
[references/assembly.md](references/assembly.md).

## Which tool

| Task | Use | Notes |
|---|---|---|
| Explore 3–6 scene directions | `scripts/grok-image.sh` | fast, sober documentary tone |
| Final still, carousel, cover | `scripts/agy-image.sh` | richer light and detail, more "AI look" |
| Still by API (agy quota out, batches) | `scripts/nano.py <model> "<prompt>"` | `gemini-nano-banana-2.1` for stills; `gemini-3-pro-image --image still.png` for fine edits — ask for changes gently, it overdoes them |
| Shot shown full-screen, 1080p | `scripts/veo.py --image still.png` | keeps the still's composition, moves the camera |
| Cheap motion draft, or a 720p final | `veo.py --model veo-3.1-lite-generate-preview --res 720p --negative ""` | the Lite model rejects `negativePrompt` |
| Premium shot | `veo.py --model veo-3.1-generate-preview` | 1080p needs `--seconds 8`; try Lite with the same prompt first — Standard can reinvent the geometry |
| Blurred background, small card, Reels background | `scripts/grok-video.sh --image still.png` | 480p by default, `--res 720p` when visible; ignores aspect ratio and follows the still |

Do not upscale a Grok clip to 1080p — frame-by-frame upscaling takes tens of
minutes per clip. If the shot needs 1080p, use Veo. Check current model names
and prices on the vendors' pages before choosing; they change monthly.

## The flow that controls composition

Text-to-video picks its own framing. Starting from a still keeps the
composition and only animates the camera:

1. **Explore** 3–6 stills with `grok-image.sh`, varying one thing at a time
   (camera height, time of day, how much horizon).
2. **Choose** on a contact sheet (`contact-sheet.sh sheet.jpg *.png`), for what
   the piece needs — room for the title, legibility on a small screen.
3. **Final still** with `agy-image.sh`, repeating the chosen prompt.
4. **Animate** with `veo.py --image` (1080p) or `grok-video.sh --image`
   (background).
5. **Check** with `contact-sheet.sh` (a video contributes 4 frames) before the
   timeline.

```bash
for alt in "mid-height drone" "high drone, nearly top-down" "low camera between the rows"; do
  scripts/grok-image.sh "compost windrows at dawn, $alt, light mist, no people, no text, 16:9" "dir-${alt// /-}.png"
done
scripts/contact-sheet.sh directions.jpg dir-*.png
scripts/agy-image.sh "<chosen direction prompt>" still.png
python3 scripts/veo.py "slow drone push forward along the windrows, mist drifting, no text" -o shot.mp4 --image still.png
scripts/contact-sheet.sh check.jpg still.png shot.mp4
```

## Prompts

- A scene, not a concept: "compost windrows at dawn, mid-height drone, light
  mist" works; "sustainability and technology" returns cliché.
- Always "no people, no text" for stills. Generated text has invented letters;
  titles go on later in the brand's type.
- State the aspect ratio in the still prompt; Veo follows the still and takes
  `--aspect 9:16` for Reels.
- Veo: English, one camera verb per shot with its framing ("medium shot, slow
  push forward"). Describe the motion; the still already holds the scene.
- Veo sound on its own line ("Audio: light wind, distant birds"); dialogue
  after a colon, not in quotes, which can become on-screen text.
- Grok image has no negative prompt field: describe what you want.
- One change per round.

## Never generate

- **The product.** Generators invent a similar device with other colors, logo
  and connectors. Use a real photo, a turntable of the model
  (`turntable-blender` skill) or Three.js, and composite it over a generated
  environment.
- **Logos, data, numbers, certificates.**
- **Real people, or people who could pass for staff or customers.** See the
  `voice-over` skill.

## Fitting it into the piece

- Generated shots are short (2–4 s) and supporting: atmosphere around real
  footage, never in place of the proof (product, dashboard, report).
- Apply the same color treatment to generated and real footage (in Remotion,
  the same CSS `filter` on both `<OffthreadVideo>`s).
- The title sits in the space the still left free — that is why the still is
  chosen for the layout.
- A blurred Grok clip (`filter: blur(6px) brightness(.6)`) hides 480p behind
  Reels typography.

## Before publishing

- Instagram reads invisible marks (SynthID, C2PA) and shows "AI info".
  Removing a visible mark does not hide it, and on Grok violates the usage
  policy.
- Watch every clip in full: errors appear mid-clip, not on the first frame.
- A series of stills of one scene drifts in detail; derive variations from one
  still by crop and motion.
