# Batch 2026-10-28-blocked-hosts-youtube — claims

**Notes, not run records.** Behind two rules in agent-fleet 1.9.0 (unreachable
pages, YouTube captions), measured by hand on 2026-10-28 on one Linux laptop.
n=1 per item.

**Blocked hosts**
- WebFetch: `www.reddit.com` and `stackoverflow.com` returned "Claude Code is
  unable to fetch from <host>"; a missing path on `lobste.rs` returned "The
  server returned HTTP 404 Not Found."
- The Claude desktop built-in browser refused `reddit.com` ("not allowed due
  to safety restrictions").
- Claude in Chrome refused `www.reddit.com` with the same message, and opened
  `stackoverflow.com/questions/tagged/docker` (`get_page_text` found no text;
  the screenshot showed the question list).
- `curl` with a browser user agent: `www.reddit.com/r/docker/` returned 200
  with an empty 8 KB shell, and `/.json` returned 403.
- On 2026-10-31, `gnu.org` returned 403 to curl and 429 to WebFetch, and the
  built-in browser read it.

**YouTube**
- yt-dlp 2026.03.17 with Node 26.5.1 as its JavaScript runtime wrote caption
  tracks for `jNQXAC9IVRw` (`en`, 217 characters) and `dQw4w9WgXcQ` (`en`,
  2089). `--sub-langs 'en.*'` also requested machine translations, and one of
  them (`en-de`) returned HTTP 429; the exact list `en,en-orig,en-en` did not.
  Signature and n-challenge solving failed without `--remote-components`, and
  the captions came through anyway.
- `yt_captions.py`: exit 0 on both videos with the counts above, exit 1 for
  `--lang pt` on `jNQXAC9IVRw`, exit 3 with no yt-dlp on PATH.
- agy 1.4.9, `gemini-3.8-flash-high`, all tools forbidden, asked for the first
  spoken sentence of a YouTube URL: it answered "NO VIDEO INPUT". Through crew
  `ask` (read-only, with and without `--web`) it tried to run a command, which
  was denied, and returned no reply.
