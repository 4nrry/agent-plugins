# Grok Imagine on grok.com

Checked on 2026-10-26, with one live run on the Ultra plan. Grok Imagine in the
web app (grok.com/imagine) makes 1080p video on the Grok subscription's pool,
which Grok Build and Hermes refuse (they stop at 720p). It has no API on the
subscription: the xAI API bills apart from it.

## Settings

The prompt box switches between Image, Video and Agent. In Video mode:

| Setting | Options |
|---|---|
| Resolution | 480p, 720p, 1080p |
| Duration | 6 s, 10 s, 15 s |
| Aspect ratio | 2:3, 3:2, 1:1, 9:16, 16:9 |

It also takes a first and a last frame, makes seamless loops, and the result
page offers Replace Audio, Regenerate, Captions and Share. A generation spends
the pool at once: there is no cost prompt.

## Driving it from an agent

- Use a browser where the user is already signed in (the desktop app's browser
  pane, Claude in Chrome, or a persistent Chrome profile under Playwright). The
  user signs in; never type their password or answer a CAPTCHA. On a cookie
  banner, reject the optional cookies.
- Set Video, the resolution, the duration and the aspect ratio before typing the
  prompt, and check them every time.
- A still or a first and last frame from disk needs a browser tool that can
  fill a file picker (Claude in Chrome's upload, Playwright's
  `set_input_files`). The desktop app's browser pane cannot; there, prompt text
  to video or have the user drop the file in.
- Downloading is the user's call; the clip stays in the account's Imagine
  library.

## Measured

One text-to-video run, 2026-10-26: 1080p, 6 s, 16:9, done in about 45 s. The
page's player reported 1904x1072 and 6.04 s: 1080p class, not 1920x1080, so
scale or crop it to the timeline's size in the edit.

## Sources

- The grok.com/imagine page itself, read in the browser on 2026-10-26.
- x.ai, "Introducing The X Subscription": API usage is billed apart from the
  subscription.
