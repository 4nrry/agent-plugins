---
name: sourced-video
description: Keeps a factual video honest when AI writes, voices and illustrates it — every spoken or shown fact tied to opened sources, rumors and single-source claims kept out, outlets that disagree shown as disagreeing, both sides with equal time, sources on screen, and a check that blocks the render. Use for a news, explainer or true-story video, deciding whether a claim can go in, reviewing a script or episode spec for unsourced claims, numbers that differ between outlets, showing sources on screen, political or election content, or a channel of AI-made videos about real events.
---

# Factual video with sources

AI makes a fact video cheap to produce and just as cheap to get wrong. The
rules below hold whatever renders the picture or speaks the voice. Write the
episode spec first ([references/spec.md](references/spec.md)) and run, from
this skill's directory:

```bash
python3 scripts/check_sources.py episodes/ep012.yaml   # exit 1 lists every problem
```

Run it before recording the voice and again before the final render. It
checks structure; whether a source really says the line is a person's call.

## What goes in

- **Two opened sources per fact**, in the voice and on screen alike. Opened
  means the page was read and says it; a link seen only in search results
  supports nothing until someone opens it (`needs_verification`).
- **Sources disagree:** say the range or both versions, each attributed
  ("15h27, segundo o G1; 15h50, segundo o Poder360"). Never pick one.
- **Single-source or unconfirmed items stay out**, recorded under `left_out`
  with the phrasings to forbid, so a later rewrite cannot slip them back in.
- **A claim made by someone** goes in as their quote, attributed. When a
  source records that it was made without evidence, that goes in too.
- **What the numbers do not say** is said when the picture would suggest a
  cause nobody proved.

## Balance

- Contested stories give each side the same screen time, text size, colour
  and distance; the camera and light do not lean toward one. `sides` in the
  spec records the seconds.
- A closing question asks about a rule or a habit, never about a candidate,
  party or campaign.

## On screen

- A source bar names the outlets on every fact shot.
- A fictional layer (a mascot, lore, an easter egg) never appears in the
  narration or captions, and a shot containing it is not labelled as fact.
- When the screen text and the recorded voice disagree, the screen text wins:
  turn that line's caption off and re-record the voice before publishing.

## People and AI

- No generated face, voice or body of a real person. Show people as
  faceless figures, documents, places or their quoted words.
- Video and voice models may refuse lines that name politicians. Do not
  reword a line to get past moderation; generate that voice with another TTS
  route and keep the text (`voice` skill).
- Declare AI at upload (`video-composition` skill,
  `references/short-form.md`).

## From spec to post

Spec → `check_sources.py` → voice → preview render → human review → final
render. The pipeline never publishes: a person approves each video after
watching the preview with the sources open. At several videos a day, that
review is the limit, not the render; it only fits when the research already
arrives with two opened sources per line.
