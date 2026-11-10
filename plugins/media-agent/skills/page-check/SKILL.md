---
name: page-check
description: Checks a web page mechanically before anyone looks at it — console errors, failed requests and broken images, horizontal overflow, text that is invisible or cut off, the weight of what loads, whether it moves at rest and whether it stops under prefers-reduced-motion — and leaves screenshots at several scroll depths and widths. Use after building or changing a landing page, prototype or any HTML page, before saying it works, when a page has animation, or when asked to verify, screenshot or measure a page. A video file is checked in video-editing; a single image in image-retouching.
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
eight defects in a page and checks that each is found.

## Order of work

1. **Run it and fix every `ERROR` first.** They are facts, not taste: a
   console or page error, a request that failed, a broken image, a page wider
   than its viewport, a weight over the budget, motion that does not stop.
2. **Read the warnings.** Text invisible on the first screen is usually
   content waiting for a script to reveal it; text cut off by its box is a
   fixed height meeting a longer string.
3. **Then look at the screenshots**, every width, top to bottom. Overlaps, a
   wrong crop, a character that came out wrong and anything about taste are
   only visible here.
4. **One fix, one run.** Re-run after each fix and say which run the claim
   "it works" comes from.

## What the motion lines mean

- `moves at rest: yes` only says two captures taken a moment apart differ.
  It does not say the motion is right. For a looping character, look at a
  frame sheet (`cutout-animation`); for a scroll effect, compare the
  screenshots at consecutive stops.
- `under reduced motion: YES` is an error. The page was loaded again with
  `prefers-reduced-motion: reduce` and still moved. CSS animations need the
  media query; an animated image or a video needs a still to swap in, because
  the browser does not stop those for you.
- A page with a clock, a caret or a video counts as moving. Say so instead of
  silencing the check.

## Weight

The total is everything the page loaded after being scrolled to the bottom,
so lazy images are counted. The five largest files are listed: start with the
first one. Pick the budget before the run, not after seeing the number.

## What it does not tell you

Chrome only, on this machine: not Safari, not Firefox, not a real phone's
speed or touch. It does not judge contrast, focus order or whether the motion
feels right. Say which of these nobody checked.
