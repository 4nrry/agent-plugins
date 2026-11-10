# Batch 2026-11-10-page-check — claims

**Notes, not run records.** Source of `skills/page-check` (media-agent
0.18.0). Measured on 2026-11-10 with Node 26.5.1 and Google Chrome
157.0.8103.50 on Linux. Nothing here compares an agent with and without the
skill.

**Planted defects.** `page-check.mjs --self-test` builds two pages. On the
clean one (a CSS animation with a reduced-motion rule, one image, 2400 px of
height) it reported no error and no warning, motion at rest, no motion under
reduced motion, and wrote three screenshots. On the other it found all eight
planted defects: a 2000 px strip (overflow, named in the message), a missing
image, a `console.error`, an uncaught exception, an animation with no
reduced-motion rule, a paragraph at `opacity: 0`, a sentence cut by a fixed
height, and no `<title>`. A 0.1 KB budget was reported as exceeded and a
500 KB one was not. 17 checks, all passing.

**One real page.** A private landing-page prototype with three animated WebP
characters, at 1440x900 and 390x844 with five stops each: 15 s for both
widths, ten screenshots, no overflow, no failed request, motion at rest, none
under reduced motion, and 3800 KB loaded, of which the three animated images
were 1540, 1064 and 725 KB. A 3000 KB budget was reported as exceeded. A hand
check of the same page earlier that day (a Playwright script looking at
overflow and broken images) agreed on those two points.

- After a run no Chrome process and no temporary profile directory were left.
  An earlier version removed the profile before Chrome had exited and left
  seven directories behind; the script now waits for the exit.
- Not measured: Chromium builds other than this Chrome, macOS and Windows, a
  page behind a login, a page that never goes network-idle, and how often the
  motion check reports motion on a page with a clock or a video.
