# Batch 2026-11-10-page-check — claims

**Notes, not run records.** Source of `skills/page-check` (media-agent
0.18.0). Measured on 2026-11-10 with Node 26.5.1 and Google Chrome
157.0.8103.50 on Linux. Nothing here compares an agent with and without the
skill.

**Planted defects.** `page-check.mjs --self-test` builds two pages. On the
clean one (a CSS animation with a reduced-motion rule, one image, white text
on a dark band, large grey text, 2400 px of height) it reported no error and
no warning, motion at rest, no motion under reduced motion, no text block
under its contrast threshold, and wrote three screenshots. On the other it
found all ten planted defects: a 2000 px strip (overflow, named in the
message), a missing image, a `console.error`, an uncaught exception, an
animation with no reduced-motion rule, a paragraph at `opacity: 0`, a sentence
cut by a fixed height, no `<title>`, pale grey text on white (over 90% of its
area under 4.5:1) and white text at 80% alpha over a band that is half dark
and half light (between 30% and 70% under). A 0.1 KB budget was reported as
exceeded and a 500 KB one was not. 23 checks, all passing.

**One real page.** A private landing-page prototype with three animated WebP
characters and text over a textured, animated background, at 1440x900 and
390x844: 31 s for both widths with contrast, 15 s without it, ten screenshots,
no overflow, no failed request, motion at rest, none under reduced motion,
and 3800 KB loaded, of which the three animated images were 1540, 1064 and
725 KB. A 3000 KB budget was reported as exceeded.

**Contrast on that page.** 32 text blocks were measured on the wide viewport
and 25 to 28 on the narrow one. Before any fix, three blocks failed on each:
the emphasised words of the heading in coral on teal (98% of their area under
3:1 at 78 px, median 2.7), a 12 px counter fixed over the page (69% under
4.5:1) and a header link (25% under). On the narrow viewport a 17 px
paragraph failed in patches (13% under, with a median of 11.2) where light
decorations passed behind it. After the fixes (a lighter coral, solid colours
in place of alpha, a darker top of the gradient, darker decorations, the fixed
counter on its own backdrop) no block failed on either viewport and one
warning was left. A hand measure of the same hero earlier that day, with a
Playwright script that hid the text and sampled the element boxes, had found
the 13 px overline at a median of 4.1 with 74% of its area under 4.5:1.

- A first version of the contrast measure divided the canvas colour by its
  alpha a second time, which over-rated see-through text; it reported the
  overline above as passing. The "before" figures for the two see-through
  blocks (the counter and the paragraph) come from that version and are
  understated; the figures for opaque text and everything after the fixes are
  not affected. The self-test now has a case for it.
- After a run no Chrome process and no temporary profile directory were left.
  An earlier version removed the profile before Chrome had exited and left
  seven directories behind; the script now waits for the exit.
- Not measured: Chromium builds other than this Chrome, macOS and Windows, a
  page behind a login, a page that never goes network-idle, and how often the
  motion check reports motion on a page with a clock or a video.
