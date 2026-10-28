#!/usr/bin/env python3
"""Caption text of a public YouTube video, through yt-dlp when it is installed.

  yt_captions.py URL [--lang en] [--json]

WebFetch on a watch page returns the page chrome, not the words. yt-dlp gets
the caption tracks; since late 2025 it needs a JavaScript runtime (Node >= 20,
Deno >= 2, Bun) for YouTube. This script never installs anything.

Tracks are requested by exact name: LANG (uploaded), LANG-orig and LANG-LANG
(automatic). A pattern such as 'en.*' also pulls machine translations and drew
an HTTP 429 on 2026-10-28. The first non-empty track in that order wins.

Exit 0 with the text; 3 when yt-dlp is missing (treat the source as
unreachable); 1 when no track yields text (a 200 with an empty body is the
usual silent failure).
"""

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def render(path):
    """Join on event boundaries: some tracks carry no spaces at segment edges."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    events = []
    for ev in data.get("events", []):
        words = "".join(seg.get("utf8", "") for seg in ev.get("segs") or []).strip()
        if words and words != "\n":
            events.append(" ".join(words.split()))
    return " ".join(events)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("url")
    p.add_argument("--lang", default="en")
    p.add_argument("--json", action="store_true", help="print {url, track, chars, text}")
    a = p.parse_args()
    ytdlp = shutil.which("yt-dlp")
    if not ytdlp:
        print("unreachable: yt-dlp is not on PATH", file=sys.stderr)
        sys.exit(3)
    runtimes = [r for r in ("node", "deno", "bun") if shutil.which(r)]
    order = [a.lang, a.lang + "-orig", "%s-%s" % (a.lang, a.lang)]
    with tempfile.TemporaryDirectory(prefix="ytcap-") as tmp:
        cmd = [ytdlp, "--skip-download", "--write-subs", "--write-auto-subs",
               "--sub-langs", ",".join(order), "--sub-format", "json3",
               "--no-warnings", "-o", str(Path(tmp) / "v.%(ext)s")]
        for r in runtimes:
            cmd += ["--js-runtimes", r]
        proc = subprocess.run(cmd + [a.url], capture_output=True, text=True, timeout=180)
        for track in order:
            f = Path(tmp) / ("v.%s.json3" % track)
            text = render(f) if f.is_file() and f.stat().st_size else ""
            if text:
                if a.json:
                    print(json.dumps({"url": a.url, "track": track, "chars": len(text), "text": text},
                                     ensure_ascii=False))
                else:
                    print(text)
                return
    print("no caption text for %s (tracks tried: %s)\n%s"
          % (a.url, ", ".join(order), proc.stderr.strip()[-600:]), file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
