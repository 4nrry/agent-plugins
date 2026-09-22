#!/usr/bin/env python3
"""Busca e baixa midia com licenca comercial (Openverse, Freesound, Pexels, Pixabay). So stdlib.

  media-search.py openverse  "ambient pad" --type audio [--n 10] [--download DIR]
  media-search.py openverse  "compost plant aerial" --type image
  media-search.py freesound  "whoosh" [--license cc0|by] [--download DIR]        # FREESOUND_API_KEY
  media-search.py pexels     "industrial plant drone" --type video|photo [--download DIR]  # PEXELS_API_KEY
  media-search.py pixabay    "wastewater treatment" --type video|photo [--download DIR]    # PIXABAY_API_KEY

Chaves vêm do ambiente (use `bws run -- media-search.py ...` ou um .env carregado antes).
Cada resultado imprime licença e atribuição; confira a licença do item antes de publicar.
"""
import argparse, json, os, sys, urllib.parse, urllib.request
from pathlib import Path

UA = {"User-Agent": "media-agent-search/1.0"}

def get(url, headers=None, params=None):
    if params:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
    req = urllib.request.Request(url, headers={**UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)

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
        sys.exit(f"{name} não está no ambiente (use bws run ou exporte a variável)")
    return v

def row(items):
    for it in items:
        print(json.dumps(it, ensure_ascii=False))

# ---------------- Openverse: sem chave; license_type=commercial ----------------
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

# ---------------- Freesound: chave; filtro license ----------------
FS_LIC = {"cc0": 'license:"Creative Commons 0"', "by": 'license:"Attribution"'}
def freesound(a):
    tok = key("FREESOUND_API_KEY")
    data = get("https://freesound.org/apiv2/search/text/", params={
        "query": a.query, "filter": FS_LIC[a.license], "page_size": a.n,
        "fields": "id,name,license,username,duration,previews,url,download", "token": tok})
    out = [{"id": r["id"], "name": r["name"], "license": r["license"], "creator": r["username"], "duration_s": r["duration"],
            "preview": r["previews"]["preview-hq-mp3"], "page": r["url"]} for r in data.get("results", [])]
    row(out)
    if a.download:  # preview HQ mp3 não exige OAuth2; o original exige OAuth2
        for r in out:
            print("→", download(r["preview"], Path(a.download) / f"freesound-{r['id']}.mp3"))

# ---------------- Pexels: chave no header Authorization ----------------
def pexels(a):
    k = key("PEXELS_API_KEY")
    if a.type == "video":
        data = get("https://api.pexels.com/videos/search", headers={"Authorization": k}, params={"query": a.query, "per_page": a.n, "orientation": a.orientation})
        out = []
        for v in data.get("videos", []):
            best = max(v["video_files"], key=lambda f: (f.get("width") or 0))
            out.append({"id": v["id"], "creator": v["user"]["name"], "duration_s": v["duration"], "w": best.get("width"), "h": best.get("height"),
                        "file": best["link"], "page": v["url"], "license": "Pexels License (comercial, sem atribuição obrigatória)"})
    else:
        data = get("https://api.pexels.com/v1/search", headers={"Authorization": k}, params={"query": a.query, "per_page": a.n, "orientation": a.orientation})
        out = [{"id": p["id"], "creator": p["photographer"], "w": p["width"], "h": p["height"], "file": p["src"]["original"], "page": p["url"],
                "license": "Pexels License (comercial, sem atribuição obrigatória)"} for p in data.get("photos", [])]
    row(out)
    if a.download:
        for r in out:
            ext = Path(urllib.parse.urlparse(r["file"]).path).suffix or ".bin"
            print("→", download(r["file"], Path(a.download) / f"pexels-{r['id']}{ext}"))

# ---------------- Pixabay: chave como parâmetro; cache 24 h obrigatório ----------------
def pixabay(a):
    k = key("PIXABAY_API_KEY")
    if a.type == "video":
        data = get("https://pixabay.com/api/videos/", params={"key": k, "q": a.query, "per_page": max(3, a.n), "video_type": "film"})
        out = []
        for v in data.get("hits", []):
            best = v["videos"].get("large") or v["videos"].get("medium")
            out.append({"id": v["id"], "creator": v["user"], "duration_s": v["duration"], "w": best["width"], "h": best["height"],
                        "file": best["url"], "page": v["pageURL"], "license": "Pixabay Content License (comercial; sem revenda avulsa)"})
    else:
        data = get("https://pixabay.com/api/", params={"key": k, "q": a.query, "per_page": max(3, a.n), "image_type": "photo", "orientation": "horizontal" if a.orientation == "landscape" else None})
        out = [{"id": h["id"], "creator": h["user"], "w": h["imageWidth"], "h": h["imageHeight"], "file": h.get("largeImageURL"), "page": h["pageURL"],
                "license": "Pixabay Content License (comercial; sem revenda avulsa)"} for h in data.get("hits", [])]
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
    a = p.parse_args(); a.fn(a)

if __name__ == "__main__":
    main()
