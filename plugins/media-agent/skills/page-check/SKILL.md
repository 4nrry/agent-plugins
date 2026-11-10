---
name: page-check
description: Checks a web page mechanically before anyone looks at it — console errors, failed requests and broken images, horizontal overflow, text that is invisible or cut off, the contrast of every text block against the pixels really behind it, the weight of what loads, whether it moves at rest and whether it stops under prefers-reduced-motion — and leaves screenshots at several scroll depths and widths. Use after building or changing a landing page, prototype or any HTML page, before saying it works, when text sits over an image, a texture or anything that moves, when a page has animation, or when asked to verify, screenshot or measure a page, its legibility or its contrast. A video file is checked in video-editing; a single image in image-retouching.
---

# Page check

A page is not checked by reading its code again. Load it, measure what a
script can measure, then look at what it cannot.

```bash
node scripts/page-check.mjs page.html -o check --budget-kb 2500
node scripts/page-check.mjs https://staging.example.com/ -o check --widths 1440x900,390x844 --stops 5
```

It needs Node 22 or later and Chrome or Chromium, and no packages. Run
`node scripts/page-check.mjs --self-test` once on a new machine: it plants
twelve defects in a page and checks that each is found, then checks the
checker itself on two pages of traps, a phone and a small local server.

Exit 0 is no error, 1 is at least one `ERROR`, and 2 means the check did not
run (no Chrome, Chrome died, bad arguments). Exit 2 says nothing about the
page: do not report it as a pass or as a finding.

## Order of work

1. **Run it and fix every `ERROR` first.** They are facts, not taste: a
   console or page error (in the page or in a frame it embeds), a request
   that failed, a broken image, a page wider than its viewport or laid out
   wider than the phone, text with too little contrast, a weight over the
   budget, motion that does not stop. `the check could not finish` means the
   page hung the browser, usually a script that never returns.
2. **Read the warnings.** Text invisible on the first screen is usually
   content waiting for a script to reveal it (a tooltip waiting for a hover
   shows up here too); text cut off by its box is a fixed height meeting a
   longer string. A dialog the page opened was accepted for you. `the network
   did not go quiet` names the request that stayed open: a stream or a poll
   is fine, an image that never answers is not.
3. **Then look at the screenshots** (`<width>x<height>-<stop>.png`; a new run
   replaces the old ones), every width, top to bottom. Overlaps, a wrong
   crop, a character that came out wrong and anything about taste are only
   visible here.
4. **One fix, one run.** Re-run after each fix and say which run the claim
   "it works" comes from.

## Contrast is measured, not computed

Text colour against the declared background colour says nothing once the text
sits on an image, a texture, a gradient or something that moves. The script
hides the text, captures what is behind it twice per screenful, and applies
the text's own alpha over every sampled pixel. Each block gets the share of
its area under its threshold (4.5:1; 3:1 for text of 24 px, or 18.66 px bold),
its lowest ratio and its median, from its worst capture.

- `low contrast` is an error when 10% or more of a block's area is under
  (`--contrast-area` changes that); `contrast dips` is a warning from 2%.
- **A median that passes is not a pass.** Text over art fails in patches: the
  line reads until a light shape passes behind it.
- **See-through text is the usual cause.** White at 80% for secondary text
  takes on whatever is behind it. Use a solid colour chosen against the
  lightest place the text can sit.
- **Keep moving things out from behind running text**, or give the text its
  own backdrop. An element fixed on screen crosses every background on the
  page, so it needs its own.
- Small or thin text needs the margin most. Raising the weight or the size is
  a fix; lowering the opacity to make it "quieter" is the bug.
- The measure ignores `text-shadow` and outlines, so text that relies on one
  reads better than its number.
- Only text that is on screen is measured: not a line under a fixed header,
  a slide clipped out of a carousel or a closed accordion. An entrance is
  given up to 2 s to finish first. The value and the placeholder of a form
  field count as text, and `-webkit-text-fill-color` is the colour when set.
- Two kinds of text are left out without a line in the report: a piece of
  text of fewer than 3 characters (an icon glyph, "OK", a short price), and
  text that is all but transparent (colour alpha times opacity under 5%),
  which is how gradient text is made. Read those in the screenshots.

## What the motion lines mean

- `moves at rest: yes` only says two captures taken a moment apart differ.
  It does not say the motion is right. For a looping character, look at a
  contact sheet (`cutout-animation`); for a scroll effect, compare the
  screenshots at consecutive stops.
- `under reduced motion: YES` is an error. The page was loaded again with
  `prefers-reduced-motion: reduce` and still moved at one of the scroll
  stops, which the message names. CSS animations need the media query; an
  animated image or a video needs a still to swap in, because the browser
  does not stop those for you.
- An error marked `only under prefers-reduced-motion` came from that second
  load alone: the branch of the script that handles reduced motion is broken.
- A page with a clock, a caret or a video counts as moving. Say so instead of
  silencing the check.

## Weight

The total is what came over the wire, frames included, after the script
scrolled down the whole page so that lazy images load. A compressed file
counts compressed; a local file has no transfer size and counts at its own.
The five largest files are listed: start with the first one. Pick the budget
before the run, not after seeing the number.

## What it does not tell you

Chrome only, on this machine: not Safari, not Firefox, not a real phone's
speed or touch. Contrast is measured for HTML text only: not text inside an
image, a canvas or SVG. Nothing is hovered, focused, clicked or typed, so a
menu, a dialog or a form state is never seen. A page that scrolls inside an
element instead of the document gets a warning and only its first screen is
checked; a page that sends itself to another address is checked as whatever
it became. It does not judge focus order, type choice or whether the motion
feels right. Say which of these nobody checked.
