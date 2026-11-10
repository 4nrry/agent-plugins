#!/usr/bin/env python3
"""Search and download commercially licensed media (Openverse, Freesound, Pexels, Pixabay). Stdlib only.

  media-search.py openverse  "ambient pad" --type audio [--n 10] [--download DIR]
  media-search.py openverse  "compost plant aerial" --type image
  media-search.py freesound  "whoosh" [--license cc0|by] [--download DIR]        # FREESOUND_API_KEY
  media-search.py pexels     "industrial plant drone" --type video|photo [--download DIR]  # PEXELS_API_KEY
  media-search.py pixabay    "wastewater treatment" --type video|photo [--download DIR]    # PIXABAY_API_KEY

API keys come from the environment, injected by a secrets manager's `run` (for example
`bws run -- media-search.py ...`), never from a .env in the repo.
Each result prints its license and attribution; check the item's license before publishing.
Pixabay answers are kept for 24 h under the user cache directory, as its terms require.
"""
import argparse, hashlib, json, os, sys, time, urllib.error, urllib.parse, urllib.request
from pathlib import Path

UA = {"User-Agent": "media-agent-search/1.0"}

def get(url, headers=None, params=None):
    if params:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
    req = urllib.request.Request(url, headers={**UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)

def cached_get(name, url, params, hours=24):
    """get(), with the answer kept for `hours` under the cache directory. The
    file name is a hash of the request without its `key`, so no key is stored."""
    ident = json.dumps([url, sorted((k, str(v)) for k, v in params.items() if k != "key" and v is not None)])
    path = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache", "media-agent", name,
                hashlib.sha256(ident.encode()).hexdigest()[:32] + ".json")
    try:
        if time.time() - path.stat().st_mtime < hours * 3600:
            return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    data = get(url, params=params)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data), encoding="utf-8")
    except OSError:
        pass                      # an unwritable cache costs a request, not the search
    return data

def download(url, dest: Path, headers=None):
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={**UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=300) as r, open(dest, "wb") as f:
        while chunk := r.read(1 << 16):
            f.write(chunk)
    return dest

def key(name):
    v = os.environ.get(name)
    if not v:
        sys.exit(f"{name} is not in the environment (use bws run or export the variable)")
    return v

def row(items):
    for it in items:
        print(json.dumps(it, ensure_ascii=False))

# ---------------- Openverse: no key; license_type=commercial ----------------
def openverse(a):
    kind = "audio" if a.type == "audio" else "images"
    data = get(f"https://api.openverse.org/v1/{kind}/", params={"q": a.query, "license_type": "commercial", "page_size": a.n})
    out = []
    for r in data.get("results", []):
        out.append({"id": r["id"], "title": r.get("title"), "license": f"{r.get('license')} {r.get('license_version') or ''}".strip(),
                    "creator": r.get("creator"), "source": r.get("source"), "url": r.get("url"), "page": r.get("foreign_landing_url"),
                    "duration_ms": r.get("duration"), "attribution": r.get("attribution")})
    row(out)
    if a.download:
        for r in out:
            ext = Path(urllib.parse.urlparse(r["url"]).path).suffix or (".mp3" if kind == "audio" else ".jpg")
            print("→", download(r["url"], Path(a.download) / f"openverse-{r['id']}{ext}"))

# ---------------- Freesound: key; license filter ----------------
FS_LIC = {"cc0": 'license:"Creative Commons 0"', "by": 'license:"Attribution"'}
def freesound(a):
    tok = key("FREESOUND_API_KEY")
    data = get("https://freesound.org/apiv2/search/text/", headers={"Authorization": f"Token {tok}"}, params={
        "query": a.query, "filter": FS_LIC[a.license], "page_size": a.n,
        "fields": "id,name,license,username,duration,previews,url,download"})
    out = [{"id": r["id"], "name": r["name"], "license": r["license"], "creator": r["username"], "duration_s": r["duration"],
            "preview": r["previews"]["preview-hq-mp3"], "page": r["url"]} for r in data.get("results", [])]
    row(out)
    if a.download:  # the HQ mp3 preview needs no OAuth2; the original does
        for r in out:
            print("→", download(r["preview"], Path(a.download) / f"freesound-{r['id']}.mp3"))

# ---------------- Pexels: key in the Authorization header ----------------
def pexels(a):
    k = key("PEXELS_API_KEY")
    if a.type == "video":
        data = get("https://api.pexels.com/videos/search", headers={"Authorization": k}, params={"query": a.query, "per_page": a.n, "orientation": a.orientation})
        out = []
        for v in data.get("videos", []):
            if not v.get("video_files"):
                continue
            best = max(v["video_files"], key=lambda f: (f.get("width") or 0))
            out.append({"id": v["id"], "creator": v["user"]["name"], "duration_s": v["duration"], "w": best.get("width"), "h": best.get("height"),
                        "file": best["link"], "page": v["url"], "license": "Pexels License (commercial use, attribution not required)"})
    else:
        data = get("https://api.pexels.com/v1/search", headers={"Authorization": k}, params={"query": a.query, "per_page": a.n, "orientation": a.orientation})
        out = [{"id": p["id"], "creator": p["photographer"], "w": p["width"], "h": p["height"], "file": p["src"]["original"], "page": p["url"],
                "license": "Pexels License (commercial use, attribution not required)"} for p in data.get("photos", [])]
    row(out)
    if a.download:
        for r in out:
            ext = Path(urllib.parse.urlparse(r["file"]).path).suffix or ".bin"
            print("→", download(r["file"], Path(a.download) / f"pexels-{r['id']}{ext}"))

# ---------------- Pixabay: key as a parameter; 24 h caching required (cached_get) ----------------
def pixabay(a):
    k = key("PIXABAY_API_KEY")
    if a.type == "video":
        data = cached_get("pixabay", "https://pixabay.com/api/videos/", {"key": k, "q": a.query, "per_page": max(3, a.n), "video_type": "film"})
        out = []
        for v in data.get("hits", []):
            best = v["videos"].get("large") or v["videos"].get("medium")
            if not best or not best.get("url"):
                continue
            out.append({"id": v["id"], "creator": v["user"], "duration_s": v["duration"], "w": best["width"], "h": best["height"],
                        "file": best["url"], "page": v["pageURL"], "license": "Pixabay Content License (commercial use; no standalone resale)"})
    else:
        data = cached_get("pixabay", "https://pixabay.com/api/", {"key": k, "q": a.query, "per_page": max(3, a.n), "image_type": "photo", "orientation": "horizontal" if a.orientation == "landscape" else None})
        out = [{"id": h["id"], "creator": h["user"], "w": h["imageWidth"], "h": h["imageHeight"], "file": h.get("largeImageURL"), "page": h["pageURL"],
                "license": "Pixabay Content License (commercial use; no standalone resale)"} for h in data.get("hits", [])]
    row(out)
    if a.download:
        for r in out:
            ext = Path(urllib.parse.urlparse(r["file"]).path).suffix or ".bin"
            print("→", download(r["file"], Path(a.download) / f"pixabay-{r['id']}{ext}"))

def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    for name, fn in [("openverse", openverse), ("freesound", freesound), ("pexels", pexels), ("pixabay", pixabay)]:
        s = sub.add_parser(name); s.set_defaults(fn=fn)
        s.add_argument("query"); s.add_argument("--n", type=int, default=10); s.add_argument("--download", metavar="DIR")
        s.add_argument("--type", default="audio" if name == "openverse" else "video", choices=["audio", "image", "video", "photo"])
        s.add_argument("--license", default="cc0", choices=list(FS_LIC))
        s.add_argument("--orientation", default="landscape", choices=["landscape", "portrait", "square"])
    a = p.parse_args()
    try:
        a.fn(a)
    except urllib.error.HTTPError as e:     # the host only: a URL can carry the key
        sys.exit(f"media-search: {urllib.parse.urlsplit(e.url or '').hostname} answered HTTP {e.code} {e.reason} "
                 "(401 or 403: the key; 429: the rate limit)")
    except urllib.error.URLError as e:
        sys.exit(f"media-search: no answer from the service: {e.reason}")

if __name__ == "__main__":
    main()
