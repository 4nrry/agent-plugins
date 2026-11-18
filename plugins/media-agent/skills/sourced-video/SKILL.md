---
name: sourced-video
description: Keeps the facts in an AI-made video honest with as much sourcing as its genre needs, and no more — news gets two opened sources per fact, rumors and single-source claims kept out, outlets that disagree shown as disagreeing, both sides with equal time and sources on screen; science and curiosity get one checked source per fact, noted in the script and kept off the screen; fiction gets none but never passes as fact. A check blocks the render. Use for a news, explainer, science, curiosity or true-story video, deciding whether a claim can go in or how much sourcing a video needs, reviewing a script or episode spec for unsourced claims, numbers that differ between outlets, showing sources on screen, political or election content, or a channel of AI-made videos about real events.
---

# Factual video with sources

AI makes a fact video cheap to produce and just as cheap to get wrong. How
much sourcing a video needs depends on what it claims: demanding sources where
nothing is claimed buys nothing and only narrows what a channel can make.
Choose the level first, then follow the rules of that level whatever renders
the picture or speaks the voice. Write the episode spec
([references/spec.md](references/spec.md)) with its `level` and run, from
this skill's directory:

```bash
python3 scripts/check_sources.py episodes/ep012.yaml   # exit 1 lists every problem; exit 2: the check did not run
```

Run it before recording the voice and again before the final render. It
checks structure; whether a source really says the line is a person's call.

## Three levels

| `level` | Videos | A fact needs | On screen |
|---|---|---|---|
| `news` (default) | news, current events, politics, elections, anything a side disputes | two opened sources; a single-source item stays out | a source bar on every fact shot; the sources also go in the post caption |
| `science` | science, curiosity, "what if", explainers, the real facts inside a story | one reliable source checked once (an official body, a study, a reference work, a specialist outlet), noted in the script | no source bar; the post caption may list the sources |
| `fiction` | invented stories, microdrama, horror, comedy | nothing for an invented line; a real fact it leans on, one source | nothing, and it never presents itself as fact |

- **Science:** what everyone knows (water boils at 100 °C at sea level) needs
  no lookup (`kind: common`); a number, a study, a date or a quote always
  needs its source. When sources disagree, use the official value or say the
  number is uncertain.
- **Fiction:** an invented line is `kind: story`. A real fact a story leans
  on is a science fact and needs its source. No real person is a character.
- **A story inside a factual video** (an invented neighbour in a brand film)
  keeps its lines as `story` in a `science` spec; the voice tells it as a
  story, never as a report.
- Do not lower the level to skip work: politics, elections and anything a
  side disputes stay `news`, whatever the channel.

## News: what goes in

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

## News: balance

- Contested stories give each side the same screen time, text size, colour
  and distance; the camera and light do not lean toward one. `sides` in the
  spec records the seconds.
- A closing question asks about a rule or a habit, never about a candidate,
  party or campaign.

## On screen

- News: a source bar names the outlets on every fact shot. Science and
  fiction: no source bar.
- A fictional layer (a mascot, lore, an easter egg) never appears in the
  narration or captions of a news or science video, and a shot containing it
  is not labelled as fact.
- When the screen text and the recorded voice disagree, the screen text wins:
  turn that line's caption off and re-record the voice before publishing.

## People and AI

At every level:

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
watching the preview, with the sources open for a news or science video. At
several videos a day, that review is the limit, not the render; it only fits
when the research already arrives with the sources its level needs.
