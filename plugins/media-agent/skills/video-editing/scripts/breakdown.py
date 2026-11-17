#!/usr/bin/env python3
"""Break a finished video down frame by frame, for a reference to learn from
or a render of your own to check before it ships.

  breakdown.py VIDEO --out DIR [--words WORDS.json] [--every 0.5] [--size 360]

Writes into DIR:
  report.md, report.json  hard cuts, change zones, flashes, sound hits,
                          loudness, silences, and each word's frame
  frames/NNNNN.jpg        every frame, SIZE px wide
  overview_NN.jpg         a contact sheet, one tile every EVERY seconds
  zone_NN.jpg             consecutive frames around each change zone

WORDS is WhisperX JSON (segments[].words[]) or a list of {word, start, end}
in seconds. Needs ffmpeg and ffprobe on PATH, numpy and Pillow.

What it cannot see: a word appearing as text on screen is a small local
change, below the zone threshold; read it off the zone and overview sheets.
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

try:
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
except ImportError as e:
    sys.exit(f"breakdown: {e.name} is not installed; it needs numpy and Pillow (pip install numpy pillow)")

SR = 48000
THUMB_W = 90          # width the frame differences are measured at
ZONE_GAP = 3          # frames: changes closer than this join one zone
ZONE_PAD = 3          # frames shown before and after a zone
ZONE_MAX_TILES = 32
FLASH_RISE = 15.0     # mean luma (0-255) gained within 2 frames
FLASH_FALL = 0.4      # share of that rise lost again within FLASH_DECAY frames
FLASH_DECAY = 12
SAME = 0.6            # correlation above which two frames show the same picture
CUT_SAME = 0.5        # correlation under which a frame has lost the previous picture
SHAPE_W = 45          # width the picture's structure is compared at
SYNC_WINDOW = 6       # frames searched around a flash for its sound


def run(cmd, **kw):
    return subprocess.run(cmd, check=True, capture_output=True, **kw)


def probe(video):
    out = run(["ffprobe", "-v", "error", "-show_entries",
               "stream=codec_type,codec_name,width,height,r_frame_rate,sample_rate,channels:format=duration",
               "-of", "json", str(video)], text=True).stdout
    info = json.loads(out)
    v = next((s for s in info["streams"] if s["codec_type"] == "video"), None)
    if v is None:
        sys.exit(f"breakdown: no video stream in {video}")
    a = next((s for s in info["streams"] if s["codec_type"] == "audio"), None)
    num, den = (int(x) for x in v["r_frame_rate"].split("/"))
    return {"width": v["width"], "height": v["height"], "fps": num / den,
            "fps_fraction": v["r_frame_rate"], "video_codec": v["codec_name"],
            "duration": float(info["format"]["duration"]),
            "audio": None if a is None else {"codec": a["codec_name"],
                                             "sample_rate": int(a["sample_rate"]),
                                             "channels": a["channels"]}}


def extract_frames(video, frames_dir, size):
    frames_dir.mkdir(parents=True, exist_ok=True)
    for old in frames_dir.glob("*.jpg"):
        old.unlink()
    run(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-vf", f"scale={size}:-2",
         "-fps_mode", "passthrough", "-q:v", "3", "-start_number", "0",
         str(frames_dir / "%05d.jpg")])
    return sorted(frames_dir.glob("*.jpg"))


class Shapes:
    """Each frame's structure: a small grey thumbnail brought to zero mean and
    unit spread, so a flash or a fade does not change it but a new picture does."""

    def __init__(self):
        self.z = []

    def add(self, im):
        a = np.asarray(im.resize((SHAPE_W, max(1, round(SHAPE_W * im.height / im.width)))), np.float32)
        self.z.append(((a - a.mean()) / (a.std() + 1e-6)).astype(np.float16))

    def corr(self, a, b):
        a, b = max(0, min(a, len(self.z) - 1)), max(0, min(b, len(self.z) - 1))
        return float((self.z[a].astype(np.float32) * self.z[b].astype(np.float32)).mean())


def picture_series(files):
    """Per frame: mean absolute difference to the previous frame and mean luma,
    plus each frame's structure."""
    diff, luma, shapes, prev = [0.0], [], Shapes(), None
    for f in files:
        im = Image.open(f).convert("L")
        a = np.asarray(im.resize((THUMB_W, max(1, round(THUMB_W * im.height / im.width)))), np.float32)
        luma.append(float(a.mean()))
        shapes.add(im)
        if prev is not None:
            diff.append(float(np.abs(a - prev).mean()))
        prev = a
    return np.array(diff), np.array(luma), shapes


def find_flashes(luma, shapes):
    """The light jumps by FLASH_RISE within 2 frames and falls back soon after,
    and the picture is the same one before and after: a flash, not a whip onto
    a brighter shot or a fade to a white card. The picture may vanish into
    white at the peak."""
    out, i = [], 2
    while i < len(luma):
        ref = i - 1 if luma[i - 1] <= luma[i - 2] else i - 2  # the last frame before the light rose
        base = luma[ref]
        if luma[i] - base >= FLASH_RISE:
            j = i
            while j + 1 < len(luma) and luma[j + 1] > luma[j]:
                j += 1
            rise = luma[j] - base
            after = luma[j + 1:j + 1 + FLASH_DECAY]
            falls = len(after) > 0 and luma[j] - after.min() >= FLASH_FALL * rise
            # Compared with the frame before the light rose and with the one just
            # before the jump: something can fall or move across either.
            refs = {ref, i - 1}
            kept = any(min(shapes.corr(r, k) for k in range(i, j + 1)) >= SAME for r in refs)
            back = len(after) > 0 and any(
                shapes.corr(r, j + 1 + int(np.argmin(after))) >= SAME for r in refs)
            if falls and (kept or back):
                out.append({"frame": j, "start": i, "rise": round(float(rise), 1)})
            i = j + 3
        else:
            i += 1
    return out


def find_cuts(d, shapes, flashes):
    """A hard cut is one frame that changes far more than its neighbours, after
    which the previous picture does not come back, and that is not a flash."""
    med = float(np.median(d[1:])) if len(d) > 1 else 0.0
    in_flash = {k for f in flashes for k in range(f["start"], f["frame"] + 1)}
    cuts = []
    for i in range(1, len(d)):
        nb = max(d[i - 1] if i > 1 else 0.0, d[i + 1] if i + 1 < len(d) else 0.0)
        if (d[i] > max(20.0, 6 * med) and d[i] > 2.5 * nb and i not in in_flash
                and shapes.corr(i - 1, i) < CUT_SAME and shapes.corr(i - 1, i + 3) < CUT_SAME):
            cuts.append(i)
    return cuts


def find_zones(d, cuts, flashes):
    med = float(np.median(d[1:])) if len(d) > 1 else 0.0
    thr = max(6.0, 3 * med)
    hot = [i for i in range(1, len(d)) if d[i] > thr]
    zones = []
    for i in hot:
        if zones and i - zones[-1][1] <= ZONE_GAP:
            zones[-1][1] = i
        else:
            zones.append([i, i])
    out = []
    for a, b in zones:
        peak = a + int(np.argmax(d[a:b + 1]))
        kind = "cut" if any(a <= c <= b for c in cuts) else \
               "flash" if any(a <= f["frame"] <= b for f in flashes) else "move"
        out.append({"start": a, "end": b, "frames": b - a + 1, "peak_frame": peak,
                    "peak_diff": round(float(d[peak]), 1), "kind": kind})
    return out, round(thr, 2)


def audio_series(video, fps):
    """Per video frame: RMS in dBFS and energy 30-150 Hz in dB."""
    raw = run(["ffmpeg", "-v", "error", "-i", str(video), "-vn", "-ac", "1", "-ar", str(SR),
               "-f", "f32le", "-"]).stdout
    x = np.frombuffer(raw, np.float32)
    hop = SR / fps
    n = int(len(x) // hop)
    rms, low = np.empty(n), np.empty(n)
    for i in range(n):
        seg = x[int(i * hop):int((i + 1) * hop)]
        rms[i] = 20 * np.log10(np.sqrt(np.mean(seg ** 2)) + 1e-9)
        spec = np.abs(np.fft.rfft(seg * np.hanning(len(seg))))
        f = np.fft.rfftfreq(len(seg), 1 / SR)
        low[i] = 20 * np.log10(spec[(f > 30) & (f < 150)].sum() + 1e-9)
    return rms, low


def jumps(series, rise, floor=None):
    """Frames where a series jumps by `rise` dB over the mean of the 3 before."""
    out, i = [], 3
    while i < len(series):
        if (floor is None or series[i] > floor) and series[i] - series[i - 3:i].mean() > rise:
            out.append({"frame": i, "jump_db": round(float(series[i] - series[i - 3:i].mean()), 1)})
            i += 3
        else:
            i += 1
    return out


def silences(rms, fps, below=-50.0, min_s=0.25):
    out, start = [], None
    for i, v in enumerate(list(rms) + [0.0]):
        if v < below and start is None:
            start = i
        elif v >= below and start is not None:
            if (i - start) / fps >= min_s:
                out.append({"start_frame": start, "end_frame": i - 1})
            start = None
    return out


def loudness(video):
    err = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(video), "-vn", "-af",
                          "loudnorm=print_format=json", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", err, re.S)
    if not m:
        return None
    j = json.loads(m.group(0))
    return {"integrated_lufs": float(j["input_i"]), "true_peak_dbtp": float(j["input_tp"]),
            "lra_lu": float(j["input_lra"])}


def load_words(path, fps):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict):
        items = [w for s in data.get("segments", []) for w in s.get("words", [])]
    else:
        items = data
    out = []
    for w in items:
        if "start" not in w:
            continue
        out.append({"word": w.get("word", w.get("text", "")).strip(), "start": float(w["start"]),
                    "frame": int(float(w["start"]) * fps)})
    return out


def font(size):
    for path in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                 "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
                 "C:/Windows/Fonts/arialbd.ttf"):
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def sheet(files, idxs, fps, dest, cols, tile_w):
    first = Image.open(files[0])
    tile_h = round(tile_w * first.height / first.width)
    rows = (len(idxs) + cols - 1) // cols
    label = 22
    s = Image.new("RGB", (cols * tile_w, rows * (tile_h + label)), "white")
    draw, f = ImageDraw.Draw(s), font(15)
    for k, i in enumerate(idxs):
        x, y = (k % cols) * tile_w, (k // cols) * (tile_h + label)
        s.paste(Image.open(files[i]).convert("RGB").resize((tile_w, tile_h)), (x, y + label))
        draw.text((x + 3, y + 3), f"f{i}  {i / fps:.3f}s", fill="black", font=f)
    s.save(dest, quality=88)


def write_md(r, dest):
    fps = r["probe"]["fps"]
    t = lambda f: f"{f / fps:.3f}"  # noqa: E731
    p = r["probe"]
    L = [f"# Breakdown: {r['video']}", "",
         f"{p['width']}x{p['height']}, {p['fps_fraction']} fps, {r['frames']} frames, "
         f"{p['duration']:.3f} s, {p['video_codec']}"
         + (f"; audio {p['audio']['codec']} {p['audio']['sample_rate']} Hz" if p["audio"] else "; no audio"), ""]
    if r.get("loudness"):
        lo = r["loudness"]
        L += [f"Loudness: {lo['integrated_lufs']} LUFS integrated, true peak {lo['true_peak_dbtp']} dBTP, "
              f"LRA {lo['lra_lu']} LU.", ""]
    L += [f"Frame difference: median {r['median_diff']}, zone threshold {r['zone_threshold']} "
          "(mean absolute difference of the grey frame, 0-255).", "",
          f"## Hard cuts: {len(r['cuts'])}", ""]
    L += [f"- f{c} ({t(c)} s)" for c in r["cuts"]] or ["None: every change is a move, a blur or a fade."]
    L += ["", "## Change zones", "", "| # | Frames | Time (s) | Kind | Peak | Sheet |", "|---|---|---|---|---|---|"]
    for k, z in enumerate(r["zones"]):
        sheet_name = z.get("sheet", "")
        L.append(f"| {k + 1} | f{z['start']}-f{z['end']} | {t(z['start'])}-{t(z['end'])} | {z['kind']} | "
                 f"{z['peak_diff']} at f{z['peak_frame']} | {sheet_name} |")
    L += ["", "## Flashes and their sound", "",
          "Offset is the sound hit's frame minus the flash's; positive means the sound comes later. "
          "A hit can read one frame early: AAC spreads a transient's energy a little before it.", "",
          "| Flash | Time (s) | Luma rise | Nearest low hit | Offset (frames) |", "|---|---|---|---|---|"]
    for fl in r["flashes"]:
        h = fl.get("low_hit")
        L.append(f"| f{fl['frame']} | {t(fl['frame'])} | {fl['rise']} | "
                 + (f"f{h} | {h - fl['frame']:+d} |" if h is not None else "none within "
                    f"{SYNC_WINDOW} frames | |"))
    if r.get("audio"):
        a = r["audio"]
        L += ["", "## Sound", "",
              "Onsets (RMS up 6 dB or more): " + ", ".join(f"f{o['frame']} ({t(o['frame'])})" for o in a["onsets"]),
              "", "Low hits (30-150 Hz up 8 dB or more): "
              + ", ".join(f"f{o['frame']} ({t(o['frame'])})" for o in a["low_hits"]),
              "", "Silences under -50 dBFS: "
              + (", ".join(f"{t(s['start_frame'])}-{t(s['end_frame'])} s" for s in a["silences"]) or "none")]
    if r.get("words"):
        L += ["", "## Words", "", "| Word | Spoken at (s) | Frame |", "|---|---|---|"]
        L += [f"| {w['word']} | {w['start']:.3f} | f{w['frame']} |" for w in r["words"]]
    dest.write_text("\n".join(L) + "\n", encoding="utf-8")


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("video")
    p.add_argument("--out", required=True)
    p.add_argument("--words", help="WhisperX JSON or a list of {word, start, end}")
    p.add_argument("--every", type=float, default=0.5, help="seconds between overview tiles")
    p.add_argument("--size", type=int, default=360, help="width of the extracted frames")
    a = p.parse_args()
    for tool in ("ffmpeg", "ffprobe"):
        if not shutil.which(tool):
            sys.exit(f"breakdown: {tool} is not on PATH")
    video, out = Path(a.video).resolve(), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    info = probe(video)
    fps = info["fps"]
    files = extract_frames(video, out / "frames", a.size)
    d, luma, shapes = picture_series(files)
    flashes = find_flashes(luma, shapes)
    cuts = find_cuts(d, shapes, flashes)
    zones, thr = find_zones(d, cuts, flashes)
    r = {"video": video.name, "probe": info, "frames": len(files),
         "median_diff": round(float(np.median(d[1:])), 2) if len(d) > 1 else 0.0,
         "zone_threshold": thr, "cuts": cuts, "zones": zones, "flashes": flashes}
    if info["audio"]:
        rms, low = audio_series(video, fps)
        hits = jumps(low, 8.0)
        r["audio"] = {"onsets": jumps(rms, 6.0, floor=-40.0), "low_hits": hits,
                      "silences": silences(rms, fps)}
        r["loudness"] = loudness(video)
        for fl in flashes:
            near = [h["frame"] for h in hits if abs(h["frame"] - fl["frame"]) <= SYNC_WINDOW]
            fl["low_hit"] = min(near, key=lambda h: abs(h - fl["frame"])) if near else None
    if a.words:
        r["words"] = load_words(a.words, fps)
    for old in [*out.glob("overview_*.jpg"), *out.glob("zone_*.jpg")]:
        old.unlink()
    step = max(1, round(a.every * fps))
    over = list(range(0, len(files), step))
    for k in range(0, len(over), 18):
        sheet(files, over[k:k + 18], fps, out / f"overview_{k // 18 + 1:02d}.jpg", 6, 240)
    for k, z in enumerate(zones):
        lo_f, hi_f = max(0, z["start"] - ZONE_PAD), min(len(files) - 1, z["end"] + ZONE_PAD)
        idxs = list(range(lo_f, hi_f + 1))
        if len(idxs) > ZONE_MAX_TILES:
            idxs = idxs[::-(-len(idxs) // ZONE_MAX_TILES)]
        z["sheet"] = f"zone_{k + 1:02d}.jpg"
        sheet(files, idxs, fps, out / z["sheet"], 8, 180)
    (out / "report.json").write_text(json.dumps(r, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_md(r, out / "report.md")
    print(f"frames {len(files)}  cuts {len(cuts)}  zones {len(zones)}  flashes {len(flashes)}  -> {out / 'report.md'}")


if __name__ == "__main__":
    main()
