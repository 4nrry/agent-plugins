# Sources: order, rules, traps

## Contents
- FACTUAL order
- META order
- Wiki pages
- Video
- Collection traps

## FACTUAL order

1. The local disk, if the question is about this install.
2. Official patch notes, newest first: the only clock.
3. Official docs, for semantics, mechanics and warnings only — never "which
   value to use". Treat them as live docs without a timestamp.
4. A wiki page that shows last-edited **and** a version tag (see below).
5. Everything else: corroboration, never the sole carrier of a number.

Prefer a JSON API to a JS-rendered page, but re-check the dates it returns:
official APIs also return impossible dates.

Steam news for an appid, studio posts only:

```bash
curl -s "https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid=$APPID&count=10&maxlength=1500" \
  | jq '.appnews.newsitems[] | select(.feedname=="steam_community_announcements") | {title, date, contents}'
```

The feed mixes press items with studio posts. A dedicated server's appid has
no feed; its notes come under the client's appid.

## META order

1. Official patch notes first, always.
2. Games sites that state both date and version.
3. Wiki, for taxonomy, names, structure and flow.
4. Forums and community, for "how it behaves in practice". A thread's date is
   a floor for its content, not a label.
5. Hosting blogs last.

A community-measured behavior number is a report, not data, unless it comes
with `n` and a method.

## Wiki pages

Judge per page, not per domain. Use a wiki number if and only if the page
shows last-edited **and** (a version tag **or** a date after the last patch
that touched the subsystem). Wikis are often the only source with per-content
version provenance; that same provenance is what lets you reject a stale page.

## Video

Video counts for META (routes, tactics, build shape), never for FACTUAL:
transcripts carry numbers with no build attached. Upload date is a real date,
so the patch fence applies. YouTube search does not sort by recency; sort or
fence before reading.

Captions need `yt-dlp` on PATH. Detect it; never install it or tell the user
to. Without it, the source is unreachable — and that is the answer.

```bash
command -v yt-dlp >/dev/null || { echo "video: unreachable"; exit 0; }
yt-dlp --skip-download --write-subs --write-auto-subs \
       --sub-langs 'en.*' --sub-format json3 -o 'v.%(ext)s' "$URL"
```

- `--sub-langs 'en.*'`, not `en`: English may exist only as `en-en` in the
  automatic pool.
- Assert a non-empty file; no-install routes return HTTP 200 with an empty
  body.
- Join json3 caption text at event boundaries, not with `"".join()` over
  segments, which drops words on some tracks.
- Expect yt-dlp's requirements to keep changing.
- Auto-captions are ASR: quote sparingly, never as a primary verbatim source.

## Collection traps

- Search engines swap the requested domain silently (`site:reddit.com` comes
  back as `steamcommunity.com`). Record the swap; never present the substitute
  as the request.
- Reddit and Fandom are not reachable by automation here; routing there
  produces the swap above.
- A footer saying "updated for X" proves nothing; check the body against X.
- Never cite as read a source seen only through a search summary.
- Check your own source list against your recency claim before stating it.
