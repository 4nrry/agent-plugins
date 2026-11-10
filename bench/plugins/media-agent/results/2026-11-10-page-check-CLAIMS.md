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
found all twelve planted defects: a 2000 px strip (overflow, named in the
message), a missing image, a `console.error`, an uncaught exception, an
animation with no reduced-motion rule, a paragraph at `opacity: 0`, a sentence
cut by a fixed height, no `<title>`, pale grey text on white (over 90% of its
area under 4.5:1) white text at 80% alpha over a band that is half dark and half light (between
30% and 70% under), black text given a white `-webkit-text-fill-color`, and a
pale grey value in a form field. A 0.1 KB budget was reported as exceeded and
a 500 KB one was not.

**Traps for the checker.** The self-test also runs a third page, with contrast
off, where the first version of the script was wrong in both directions. It
has to find a spinner at the top of a 3000 px page that ignores reduced
motion, a lazy image at the bottom that is missing (reported once, not
twice), a `console.error` raised only when `prefers-reduced-motion` matches,
and an `alert()`; and it must not report a screen-reader-only link as cut
text, an off-canvas menu behind `overflow-x: hidden` as overflow, or a
sentence that fades in after 0.9 s as invisible. A page with no viewport meta
at 390 px must be named as that, not as overflow. A local server checks that
a redirect and a missing `/favicon.ico` are not errors, that a 300 KB script
sent gzipped counts under 50 KB, and that a frame from another site has its
console error and its missing image reported.

A fourth page holds the traps of the contrast measure, all of them text that
reads well or is not on screen: 40 dark paragraphs scrolling under a fixed
dark header, a white carousel slide clipped away, a closed accordion in white,
paragraphs with `transition: all 1s`, and paragraphs that fade in when
scrolled to. It must raise nothing. On the phone page, white text on a dark
panel must not fail because the capture is 390 px wide and the layout 980.
44 checks, all passing, in 65 s.

**One real page.** A private landing-page prototype with three animated WebP
characters and text over a textured, animated background, at 1440x900 and
390x844: 49 s for both widths with contrast, 38 s without it, ten screenshots,
no overflow, no failed request, motion at rest, none under reduced motion,
and 3800 KB loaded, of which the three animated images were 1540, 1064 and
725 KB. A 3000 KB budget was reported as exceeded. The first version took 31 s
and 15 s: it captured each stop once and checked reduced motion on one screen.
The same file without the wrapper that adds its viewport meta was reported as
laid out 980 px wide on the 390 px screen.

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
- **A cold review of the first version** by a subagent that only had the diff
  found 17 defects and reproduced each. What follows was run again on the
  fixed script, on the reviewer's own pages and server.
- Failing without saying so. With Chrome killed mid-run the first version
  exited 0 with no output; now it exits 2 with a message. A page in an endless
  loop, an `alert()` and an image whose server never answers each hung it for
  good; now 31 s and an error (`the check could not finish`), 4 s and a
  warning, 27 s and a warning that names the request.
- Leftovers. SIGTERM, SIGINT and `timeout` left Chrome or its profile behind,
  and so did a Node without WebSocket, `CHROME=/bin/false` and a `CHROME` that
  is not executable. Now each ends with Chrome gone and no directory, the last
  three with exit 2 and a message. Chrome also scattered directories of its
  own in the system temp directory, one or two per run: it now gets a `TMPDIR`
  inside the run's directory, and after twelve runs in a row the count there
  had not changed. `kill -9` on the script itself still leaves Chrome running.
- Waiting. A redirect was counted as two requests in flight and held every
  wait to its 15 s limit: 32 s for a plain page behind a 302, now 3.8 s. A
  page that polls or keeps an event stream open took the same 32 s in silence;
  it takes 21 s and a warning.
- Weight. A 1 MB script sent gzipped was counted as 1024 KB; now 2 KB. A
  300 KB lazy image at the bottom that takes 3 s to arrive was counted as 0;
  now 301 KB. A frame from another site was invisible (1 KB, none of its
  errors); now its console error and its 404 are reported and its bytes
  counted.
- Scrolling. Lazy images were only loaded when contrast was on, and reduced
  motion was checked on whatever screen the reload landed on, so a spinner at
  the top of a tall page passed with `--no-contrast`. Both now hold with
  contrast off. An error raised only by the reduced-motion load was thrown
  away with the repeats; it is kept and marked.
- False alarms removed: the browser's own request for `/favicon.ico`, content
  clipped by `overflow-x: hidden` or `clip` on the page, a screen-reader-only
  link, `-webkit-line-clamp`, an entrance animation that had not started, a
  second error for an image whose request had already failed. A tooltip at
  `opacity: 0` is still listed as invisible text; nothing is hovered.
- **A second cold review**, of the contrast measure and of the fixes above,
  reproduced eight more; each failed on the previous commit and passes now.
  Six were in the contrast measure. It read the pixels of a fixed header as
  the background of the text scrolling under it (14 of 121 paragraphs
  failing on a page of dark text on white), and of whatever sat where
  clipped text would have been. It caught text halfway through a fade-in
  (alpha 0.51). Hiding the text started the page's own colour transition, so
  the glyphs were still in the capture (a heading at 19% under). On a phone
  page with no viewport meta it indexed a 390 px capture with 980 px
  coordinates. It ignored `-webkit-text-fill-color` and form fields, a false
  pass. And it could not finish on an SVG document. The other two: a worker's
  `console.error` was reported twice, and the cleanup of old screenshots
  removed any file in the output directory with a name of the same shape; it
  now removes only what the earlier report lists.
- Not fixed: a page that navigates itself away is checked as the page it
  became; a page that scrolls inside an element gets a warning and one
  screen; `console.error` of an object prints `Object`; a text caret counts as
  motion; the self-test needs Chrome, so the repository's validator does not
  run it.
- Not measured: Chromium builds other than this Chrome, macOS and Windows, a
  page behind a login, a page that never goes network-idle, and how often the
  motion check reports motion on a page with a clock or a video.
