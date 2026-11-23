# Caption looks and caption craft

Seventeen caption looks as numbers you can apply, and the rules for how many
words to show, when, where and how big. Use it when `SKILL.md` says captions
carry the voice and you now have to choose and build one.

Source: [`vargHQ/skills`](https://github.com/vargHQ/skills), folder
`caption-styles/`, MIT, Copyright (c) 2026 vargai Inc., read at commit
`55ac28d4b4f336f9235df38d1d7aa639e4bec942` (2026-11-18). Files read:
`SKILL.md`, `references/_shared-caption-craft.md`, `references/sources.md` and
all 17 `assets/presets/*.json`. The preset numbers below are data from those
files; the prose is paraphrased. The repo cites Netflix and BBC subtitle
guides, the DCMP Captioning Key, ITU-R BT.1359, an eye-tracking study and
posts by short-form editors; those sources were not re-opened here.

**Not yet run here:** no preset was built or rendered. The repo targets
HyperFrames 0.8 or Remotion 4 and says plain looks also burn in with ffmpeg
and ASS. The caption rules are its claims and house values, not our
measurements.

## Contents

- [Order of decisions](#order-of-decisions)
- [The 17 looks](#the-17-looks)
- [Fonts and licences](#fonts-and-licences)
- [Craft rules not in SKILL.md](#craft-rules-not-in-skillmd)
- [Where it disagrees with this plugin](#where-it-disagrees-with-this-plugin)

## Order of decisions

1. Word times from the voice JSON or an aligner, never from text length (the
   `audio` skill has the aligner).
2. Chunking: phrase, group or single word (below).
3. Then the look, from the table.
4. Then check contrast and the safe box on a phone-size still.

## The 17 looks

Values are from each file's first preset (the one the repo treats as the
default); the other presets change colour, size or motion a little and are
named in the last column. Sizes are px on a 1080 by 1920 frame unless a cell
says 16:9. "Active word" is the word being spoken. Every look also lists a
plain "calm" or no-highlight preset for the accessible version.

| Look (file name) | Font | Size | Case | Box or outline | Animation | Use it for |
|---|---|---|---|---|---|---|
| `translucent-box-subtitles` | Inter 600 | 67 (16:9, 6.25% of height) | Sentence | Black box at 75%, square, 2 lines, 42 chars | Cut on and off, no motion; 0.83 to 7 s per caption | Long podcasts, interviews, courses, the accessible deliverable |
| `line-hug-box-captions` | Plus Jakarta Sans 800 | 80 (4.2%) | Sentence; the navy preset is spaced caps | White box that hugs each line, radius 0.28 em, #111 text | Box scales from 0.92 to 1 in 6 frames | Talking-head ads, how-to; presets: black inverse, navy pill rise, brand tint |
| `sliding-pill-captions` | Montserrat 900 | 84 (4.4%) | Sentence | White with 9 px black stroke; pill #1F5BFF | Pill slides to the next word in 5 frames, text stays still | Podcast clips, explainers |
| `active-word-pop-captions` | Montserrat 900 | 88 (4.6%) | Sentence | White, 10 px black stroke | Active word #4DA3FF, scale 1.12 over 4 frames then 1.06, back to 1 in 3 | Creator clips, hype ads; presets: subtle (1.06), rubbery spring |
| `active-word-color-captions` | Montserrat 800 | 84 | Sentence | White, 9 px black stroke | Colour change only (#4DA3FF), no scale | Podcast clips, comedy timing; yellow #FFE600 preset |
| `gradient-word-captions` | Poppins 800 | 84 | Sentence | Dark box at 82%, radius 0.36 em | Active word fills with a gradient #5AA9FF to #FF5EDB | Music promos, launches, creator brands; presets: sunset, sweep fill |
| `white-card-captions` | Inter 700 | 56 (16:9, 5.2%) | Sentence | White card, radius 20 px, soft shadow, #111 text | Fade in with 6 px rise, 6 frames; active word #1D4ED8 | SaaS, corporate, LinkedIn, education |
| `serif-italic-captions` | Instrument Serif 400 | 96 (5%); 72 at 16:9 | Sentence | No box, soft shadow | Active word turns italic by a 3-frame crossfade | Documentary, luxury, essays, narration |
| `frosted-panel-captions` | Inter 700 | 80 | Sentence | Blur 20 px glass, dark tint at 45%, radius 28 px | Inactive words at 80% opacity, active at 100% with a soft glow | Tech, product, lifestyle over rich footage; a thick-glass preset for bright shots |
| `neon-tube-captions` | Nunito 900 | 84 | Sentence | Dark box at 85%, 3 px pink border, glow | Halo layers on the active word; a pulse-only preset breathes once per 2 s | Nightlife, music, gaming, events |
| `bounce-word-pill` | Montserrat 900 | 120 (6.25%) | Upper | White word in a #6D28D9 pill, fully rounded | One word; spring up and scale 0.85 to 1 in 12 frames, 2-frame exit | Hooks and ad openers of 20 s or less |
| `shadow-minimal-captions` | Inter 600 | 76; 60 at 16:9 | Sentence | No box; three-layer black shadow | Active word 100% against 80%, in 2 frames | Cinematic vlogs, travel, calm brand films |
| `karaoke-fill-captions` | Poppins 800 | 84; 64 at 16:9 | Sentence | White, 8 px black stroke, yellow underline bar | Yellow wipes across each word; the line appears 15 frames early | Lyrics, sing-alongs, rhythmic voice-over; an instant-fill preset for speech |
| `outline-spring-captions` | Montserrat 900 | 88 (4.6%) | Sentence; the Anton preset is caps at 110 | White, 12 px black stroke, drop shadow | Active word cyan #00FFFF, rises 0.12 em on a spring over 8 frames | Gaming, reactions, commentary |
| `word-tile-captions` | Archivo Black 400 | 78 | Sentence | A dark tile per word; active tile #FF7A1A with dark text | Optional left-to-right stagger | Listicles, tech and finance tips |
| `tilted-card-word-pop` | Anton 400 | 140 (7.3%) | Upper | Cards alternate white and lime #C6FF3D, tilted -4 and +3 degrees | One word; scale 0.6 to 1 with overshoot in 8 frames | Hooks, memes, beat-cut promos |
| `grow-highlight-captions` | Montserrat 900 | 86 | Sentence | Dark box at 78%, radius 0.4 em | Active word yellow #FFD400 grows 0.9 to 1 in 4 frames; box width tweens in 5 | Business podcasts, coaching ads |

Words per screen, from the same files: 2 to 4 for the pop, gradient and grow
looks; 3 to 5 for the pill and colour looks; 3 to 6 for frosted; 2 to 6 for
line-hug; 4 to 7 for serif italic; one word for bounce and tilted card.
Where a preset sets them, the block centre sits at 55 to 62% of the frame
height and the 9:16 line is capped at 696 px, with these exceptions. Block
centre is set only by pop (60), bounce (58), grow (60), line-hug (62),
sliding pill (60), tilted card (55), translucent (60) and white card (60).
A 696 px cap is set only by colour, pop, frosted, gradient, grow, line-hug,
sliding pill and translucent; word tile sets 760 px; white card and
translucent also cap at 68% of width for 16:9. Bounce, karaoke, neon,
outline, serif italic, shadow and tilted card set neither a width nor a
centre, so take both from the shared table below.

## Fonts and licences

All 15 families in the presets are listed as OFL-1.1 in the preset files. I
checked each against its `METADATA.pb` in
[`google/fonts`](https://github.com/google/fonts) (commit
`06bfe0d62a98375cb09c942fa18e68bd32cff057`, 2026-11-20): all 15 sit under
`ofl/` with `license: "OFL"`.

| Family | Default in | Alternate in | Licence |
|---|---|---|---|
| Montserrat | pop, colour, pill, outline, grow, bounce | karaoke | OFL |
| Inter | translucent, frosted, white card, shadow | line-hug, colour, word tile | OFL |
| Poppins | gradient, karaoke | colour, pop, pill, grow | OFL |
| Archivo Black | word tile | bounce, tilted card | OFL |
| Anton | tilted card, outline (caps preset) | none | OFL |
| Plus Jakarta Sans | line-hug | none | OFL |
| Nunito | neon | none | OFL |
| Outfit | none | gradient, neon | OFL |
| Manrope | none | frosted | OFL |
| Figtree | none | shadow, white card | OFL |
| Instrument Serif, Playfair Display, Fraunces | serif italic (one per preset) | none | OFL |
| Atkinson Hyperlegible | none | translucent | OFL |
| Bebas Neue | none | tilted card | OFL |

What OFL means for us: the fonts may be used and embedded in a rendered video
commercially, with no attribution needed in the video. The repo says the same.
If you redistribute a font file itself, keep its `OFL.txt` and its Reserved
Font Name rules; read the licence text in the font's folder. Anything
a brand supplies, and the "Bold Font" named in `motion.md`, is outside this
table: check its licence per use.

## Craft rules not in SKILL.md

`SKILL.md` already says: captions come from the voice JSON, emphasis is rare,
keep them off mouths and under the platform buttons, 1 to 3 words per chunk
for talking heads, swaps 2 frames before the word. These add to it.

**Chunking.** Choose it before the look.

| Mode | On screen | Use for | Avoid for |
|---|---|---|---|
| Phrase | 5 to 12 words, 1 or 2 lines (3 in 9:16) | Podcasts, courses, anything over 60 s, accessible versions | Nothing: the safe default |
| Group | 2 to 5 words | Talking-head shorts, ads, explainers of 15 to 90 s | Dense numbers, legal text |
| Single word | 1 word | Hooks (first 1 to 3 s), punchlines, beat cuts, clips of 20 s or less | Long talks, names, prices, steps, lists |

- Build pages from word times: join tokens up to about 1.2 s, break on a
  silence of about 400 ms (the repo credits Remotion's
  `createTikTokStyleCaptions` for this).
- Break lines on grammar even inside a 3-word page: never split an article
  from its noun, a preposition from its phrase, a pronoun from its verb, an
  auxiliary from its verb, or a first name from a last name.
- One word at a time costs comprehension. In the study the repo cites,
  viewers spent about 90% of the time on the text. At 180 words per minute a
  word lasts about 10 frames (0.33 s) at 30 fps; faster speakers leave 6 to 8,
  too few to read and look at a face. So: single-word mode only for hooks and
  short beat clips, merge a word under 8 frames into the next card, and never
  show numbers, names, prices or steps one word at a time.

**Timing at 30 fps.**

- A caption appears on the first audio frame or within 1 to 2 frames. It goes
  about 0.5 s after the audio when nothing follows. Leave at least 2 frames
  between captions and close gaps under 0.5 s.
- The active word switches 1 to 2 frames (33 to 67 ms) before its onset. The
  repo says a picture 125 ms early goes unnoticed and a picture 45 ms late is
  noticed (ITU-R BT.1359). Check that there is voice under every caption
  within about 120 ms.
- Karaoke: the line appears 10 to 20 frames early, never more than 1.5 s; the
  fill starts 1 frame early and sweeps over the word's length.
- The source's guideline: per-word motion takes 6 frames or fewer,
  entrances 4 to 8 frames, exits about 30% shorter. Some of its own presets
  exceed it: bounce pill (12-frame spring), the spring-pop preset (12),
  navy pill rise (10), tilted card (8), outline spring (8; 12 for the Anton
  preset) and the soft pill (7). Animate scale with a transform, never `font-size`.
- Reading speed: 160 to 180 words per minute, at most 20 characters per
  second for adults (17 for children), 0.83 to 7 s per caption.

**Size and position.**

| | 16:9, 1920 by 1080 | 9:16, 1080 by 1920 |
|---|---|---|
| Plain baseline | font about 67 px (6.25% of height) | font about 67 px (3.5%) |
| Group looks (house values) | 56 to 72 px | 80 to 96 px (4.2 to 5%) |
| Single-word looks | 96 to 120 px | 110 to 150 px (5.7 to 7.8%) |
| Line | 68% of width, 42 characters, 2 lines | 696 px centred, about 13 to 22 characters, 3 lines at most |
| Block | bottom centre, inside the central 90% by 75% | centre at 58 to 62% of height, bottom edge at or above 1248 px |

- The 9:16 safe box is the worst case of the platforms' ad specs: 288 px top,
  672 bottom, 120 left, 192 right. The bottom figure matches the Meta margin
  in [short-form.md](short-form.md). The larger short-form sizes are the
  repo's own house values; verify on a phone held at arm's length, with 60 px
  or more from every edge.
- Sit a little higher in 9:16 than in 16:9, because faces live in the top
  half.

**Colour and contrast.**

- At least 4.5:1 between the text and what is directly behind it. The repo
  lists measured pairs: white on black 21:1; yellow #FFE600 on black 16.6:1;
  cyan 16.8:1; #4DA3FF on black 8.0:1; white on #1F5BFF 5.25:1; white on
  #6D28D9 7.1:1; #0A0A0A on lime #C6FF3D 16.8:1. Two fail: #2563EB on black
  (4.1:1) and white on orange #FF7A1A (2.6:1, so use dark text on orange).
- A black box over a white frame: 50% gives 4.0:1 (fails), 60% gives 5.7:1,
  75% gives 10.4:1. Glass needs a 55 to 65% dark tint plus a text shadow on
  bright footage.
- One highlight colour reads best for viewers who depend on captions. Never
  more than 3 flashes per second.

**Type.**

- Sans serif, medium to black, mixed case. Caps only for a single word or
  for stress. Outlines: `-webkit-text-stroke` with `paint-order: stroke
  fill`, about 0.1 to 0.14 em.
- Italics for a word or two, never a line.

**Delivery.**

- Ship a plain phrase version (the `translucent-box-subtitles` look) beside
  any styled render, as an accessible deliverable and a .srt or .vtt. Styled
  word-tracking captions amplify body language but cost some viewers the
  message, and two deaf or hard-of-hearing viewers quoted in the repo's sources
  say highlights hijack their eyes.
- Do not copy a trend look when the brand has its own type and colour.
- Every value must be a function of timeline time; seed any randomness by
  frame (the same rule as [hyperframes.md](hyperframes.md)).

## Where it disagrees with this plugin

- `SKILL.md` says 1 to 3 words per chunk for a talking head (from
  `herk-edit-kit`). The source's Group mode for talking-head shorts is 2 to
  5 words, and its presets run 2 to 4 (pop, gradient, grow), 3 to 5 (colour,
  pill) and up to 6 (frosted, line-hug). Start at 1 to 3 for a fast talker
  and widen only if the text cannot keep up.
- [motion.md](motion.md) adds one word every 0.14 s (4 frames at 30 fps).
  There the line builds up and earlier words stay on screen, so the 8-frame
  minimum above, which is about one word replacing another, does not apply.
  Showing one word at a time at that pace would break it.
- The "Hormozi" look in `motion.md` (heavy sans, word by word, one yellow or
  green key word) is the single-word or group mode here. The repo advises
  mixing it with a plain phrase version, not using it for long videos.
- The 4.5:1 contrast and the 60-px edge margin are checkable. If you build
  captions in a page, `page-check` measures contrast against the pixels
  really behind the text, which is a stronger test than the pairs above.
