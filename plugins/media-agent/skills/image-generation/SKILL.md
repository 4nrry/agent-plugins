---
name: image-generation
description: Generates images for a marketing piece with any image model — explore, choose on a contact sheet, final still, edits, and what never to generate. Use for a generated image, scene, still, cover, moodboard or storyboard frame, or when an image model is named (Grok Imagine, Gemini, Nano Banana, FLUX).
---

# Image generation

Generating is the cheap step; choosing and fitting make the piece. The rules
below hold for any image model. How to run each tool, and what it is good at,
is in [references/tools.md](references/tools.md).

## The flow

1. **Explore** 3–6 directions with the fastest model, varying one thing at a
   time: camera height, time of day, how much horizon.
2. **Choose** on a contact sheet, for what the piece needs: room for the title,
   legibility on a phone. From this skill's directory:
   `scripts/contact-sheet.sh sheet.jpg dir-*.png`.
3. **Final still** with the model that renders the most detail, repeating the
   chosen prompt (and seed, where the model takes one).
4. **Edit** with an editing model only for small changes, asked for gently:
   editing models overdo whatever they are told.
5. **Variations** of one scene come from the chosen still, by crop or by
   animating it (`video-generation` skill). Regenerating drifts the details.

## Prompts

- A scene, not a concept: "compost windrows at dawn, mid-height drone, light
  mist" works; "sustainability and technology" returns cliché.
- Name the aspect ratio in the prompt or the request.
- Ask for "no people, no text". Where the model has no negative prompt field,
  describe what the frame contains instead of what it lacks.
- Write prompts in English; most models follow it best.
- One change per round, so you know what changed the result.

## Never generate

- **The product.** Generators invent a similar device with other colors, logo
  and connectors. Use a real photo or a render (`3d-turntable` skill) and
  composite it over a generated environment.
- **Text, logos, data, numbers, certificates.** Generated letters are
  invented; titles go on later in the brand's type.
- **Real people, or people who could pass for staff or customers.**

## Fitting it into the piece

- Generated images are atmosphere around real material, never the proof
  (product, dashboard, report).
- Give generated and real images the same color treatment.
- The title sits in the space the still left free; that is why the still is
  chosen for the layout.

## Before publishing

- Check the model's terms for commercial use before the final still, not after.
- Generators embed provenance: an invisible watermark (SynthID on Google's
  models) and often C2PA metadata, from which Instagram shows "AI info".
  Removing a visible mark does not remove them and can break the tool's terms.
- Look at every final image at 100%: hands, edges and repeated textures fail
  where the thumbnail looks fine.
