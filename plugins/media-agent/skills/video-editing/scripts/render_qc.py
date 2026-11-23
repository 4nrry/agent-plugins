#!/usr/bin/env python3
# Adapted code and re-implemented thresholds, each named where it is used below:
#   vargHQ/skills, media-judge/scripts/mj_frames.py and mj_compress.py
#     MIT License, Copyright (c) 2026 vargai Inc.
#     (flash_safety transition counting, black_frames, glitch_frames, upload_banding's CAMBI call)
#   XuHo-IT/Content-Agent-Kit, scripts/video/lib/blank-check.mjs, lib/delivery-specs.mjs,
#     delivery-check.mjs and font-check.mjs
#     MIT License, Copyright (c) 2026 content-agent-kit contributors
#     (luma-range blank test, hard/soft split of platform limits, rotation-aware probe, glyph coverage idea)
#   lemomo-ai/lemo-opuscar, core/render/readcheck.mjs
#     MIT License (REUSE.toml: "2026 Lemomo (LemoLab)")
#     (reading-time rule: CJK / 4.5 + other / 15 + 1.5 s, never under 1.5 s; pass: true is listed, not timed)
# Each of those MIT licences asks that its copyright notice and permission notice
# travel with substantial portions: the full texts are in THIRD_PARTY_NOTICES.md
# beside this script.
"""Check a rendered video mechanically before anyone watches it.

  render_qc.py all VIDEO [--platform reels|tiktok|shorts] [--captions CAPS.json] [--font FONT] [--json]
  render_qc.py flash VIDEO        WCAG 2.3.1 general and red flash, with the 25% area rule
  render_qc.py blank VIDEO        stretches where the frame is one flat colour
  render_qc.py frames VIDEO       black seam frames and one-frame glitches
  render_qc.py banding VIDEO      CAMBI banding (needs ffmpeg built with libvmaf)
  render_qc.py delivery VIDEO --platform reels,tiktok,shorts
  render_qc.py reading [VIDEO] --captions CAPS.json
  render_qc.py fonts --font FILE_OR_FAMILY (--captions CAPS.json | --text TEXT)
  render_qc.py --self-test

CAPS.json is the voice JSON ([{id, text, say, start, duration}]), a list of
{text, start, end} (t0/t1 also read), or WhisperX JSON (its segments). A
word-level list ({word, start, end}) is not judged: one word is not a text a
viewer reads. An item with "pass": true is listed and not timed; an item
without readable start and end times is counted and reported, not timed.

Exit 0 when every check that ran passed or warned. Exit 1 when any check
failed. Exit 2 when nothing failed but a check could not run (status
"error": an unreadable or partly undecodable file, a font that cannot be
read, an ffmpeg call that failed) or nothing was checked at all; skipped
checks (an input not given, libvmaf missing) do not count as errors. A
file that fails to decode is reported as an error, never as a pass.

Every threshold and platform number carries its source in the code;
platform numbers checked 2026-11-23. Needs ffmpeg and ffprobe on PATH and
numpy; fonts falls back to fc-query for WOFF2.

Known limits: a .ttc collection is read at face 0 only, and cmap format 2
(legacy double-byte CJK encodings) is not parsed, so such a font can be
reported as missing glyphs it has.
"""

import argparse
import json
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import unicodedata
import zlib
from pathlib import Path

try:
    import numpy as np
except ImportError as e:
    if "--self-test" in sys.argv and isinstance(e, ModuleNotFoundError) and e.name in ("numpy",):  # the repo's CI is stdlib-only: skip, loudly, like the hook checks do
        print(f"self-test skipped: {e.name} not installed, and without it the script does nothing")
        sys.exit(0)
    print(f"render_qc: {e.name} is not installed; it needs numpy", file=sys.stderr)
    sys.exit(2)

# ---------------------------------------------------------------- thresholds
# Flash: WCAG 2.2 SC 2.3.1 and its glossary entry "general flash and red flash
# thresholds", https://www.w3.org/TR/WCAG22/ (read 2026-11-23).
FLASH_DELTA = 0.10        # opposing changes of relative luminance of 10% or more of 1.0
FLASH_DARK_MAX = 0.80     # ... where the darker state is below 0.80
FLASH_MAX_PER_S = 3       # more than three flashes in any one second fails
RED_RATIO = 0.8           # red flash: one state has R/(R+G+B) >= 0.8 ...
RED_UV = 0.2              # ... and the states differ by more than 0.2 in CIE 1976 u'v'
GRID = 24                 # cells per side; WCAG's 10-degree field is 341x256 of 1024x768,
FIELD = 8                 # i.e. one third of each side: 8 of 24 cells
FIELD_AREA = 0.25         # flashing area over 25% of that field
SIDE = 144                # frames are measured at 144x144 (6x6 px per cell)
# Black seam and glitch frames: vargHQ media-judge thresholds.json, all "calibrated_on_fixtures".
BLACK_LUMA, BLACK_STD, BLACK_P99, BLACK_MAX_S = 16.0, 6.0, 40.0, 0.25
GLITCH_MIN_MAD, GLITCH_MIN_CELL, GLITCH_RETURN = 6.0, 18.0, 0.35
# Blank: XuHo blank-check.mjs FLAT_RANGE (YMAX-YMIN under 20 is one flat colour;
# measured there: good scenes 171-175, blank ones 0-4). Run lengths are ours.
FLAT_RANGE = 20
BLANK_RATE = 4            # samples per second
BLANK_MIN_S = 1.0         # a flat stretch this long fails ...
BLANK_EDGE_S = 1.5        # ... unless it touches the start or end and is a fade this short
# Banding: CAMBI 5 "starts to annoy", 24 worst seen (Netflix vmaf resource/doc/cambi.md);
# the 1.5x bright factor and the dark limit of luma 60 are vargHQ fixtures. vargHQ
# compares a shot's median luma with 60; this file has no shots, so it compares
# each sampled frame's mean luma (0-255) with 60.
CAMBI_VISIBLE, CAMBI_BRIGHT_FACTOR, DARK_LUMA = 5.0, 1.5, 60.0
# Reading time: lemo-opuscar readcheck.mjs defaults.
LATIN_CPS, CJK_CPS, READ_PAD, READ_MIN = 15.0, 4.5, 1.5, 1.5

# ---------------------------------------------------------------- delivery limits
CHECKED = "2026-11-23"
U_IG_ADS = "https://www.facebook.com/business/ads-guide/update/video/instagram-reels"
U_IG_REELS = "https://about.instagram.com/features/reels"
U_TT_API = "https://developers.tiktok.com/doc/content-posting-api-media-transfer-guide"
U_TT_ADS = "https://ads.tiktok.com/help/article/video-ads-specifications"
U_YT_SHORTS = "https://support.google.com/youtube/answer/15424877"
U_YT_ENC = "https://support.google.com/youtube/answer/1722171"
U_YT_SIZE = "https://support.google.com/youtube/answer/71673"
UNCONFIRMED = "unconfirmed"
GB = 1024 ** 3
# platform, limit, value, level, source (checked CHECKED), note.
# A limit whose source is "unconfirmed" is never more than a warning.
DELIVERY = [
    ("reels", "max_duration_s", 1200, "fail", U_IG_REELS, "FAQ: up to 20 min (the same page's overview still says 3 min)"),
    ("reels", "recommend_max_s", 180, "warn", U_IG_REELS, "over 3 min is not recommended to new audiences"),
    ("reels", "containers", ("mp4", "mov"), "fail", U_IG_ADS, "Reels ads spec: MP4, MOV"),
    ("reels", "video_codecs", ("h264",), "warn", U_IG_ADS, "Reels ads spec: H.264"),
    ("reels", "constant_fps", True, "warn", U_IG_ADS, "Reels ads spec: fixed frame rate"),
    ("reels", "aspect", (9 / 16,), "warn", U_IG_ADS, "Reels ads spec: 9:16"),
    ("reels", "max_bytes", 4 * GB, "fail", U_IG_ADS, "Reels ads spec: 4 GB"),
    ("reels", "audio_codecs", ("aac",), "warn", U_IG_ADS, "Reels ads spec: AAC stereo, 128 kbps or more"),
    ("reels", "audio_channels", 2, "warn", U_IG_ADS, "Reels ads spec: stereo"),
    ("reels", "audio_min_kbps", 128, "warn", U_IG_ADS, "Reels ads spec: 128 kbps or more"),
    ("reels", "note", "1440x2560 recommended; keep text out of the top 14%, bottom 35% and 6% each side (not measured here)",
     "info", U_IG_ADS, ""),
    ("tiktok", "max_duration_s", 600, "fail", U_TT_API, "Content Posting API: 10 min"),
    ("tiktok", "containers", ("mp4", "webm", "mov"), "fail", U_TT_API, "MP4, WebM, MOV"),
    ("tiktok", "video_codecs", ("h264", "hevc", "vp8", "vp9"), "fail", U_TT_API, "H.264, H.265, VP8, VP9"),
    ("tiktok", "fps_range", (23, 60), "fail", U_TT_API, "23 to 60 fps"),
    ("tiktok", "dim_range", (360, 4096), "fail", U_TT_API, "360 to 4096 px each side"),
    ("tiktok", "max_bytes", 4 * GB, "fail", U_TT_API, "4 GB"),
    ("tiktok", "aspect", (9 / 16,), "warn", U_TT_ADS, "in-feed ads: 9:16 recommended"),
    ("tiktok", "min_res", (540, 960), "warn", U_TT_ADS, "in-feed ads: 9:16 at 540x960 or more"),
    ("tiktok", "min_kbps", 516, "warn", U_TT_ADS, "in-feed ads: 516 kbps or more"),
    ("tiktok", "app_max_bytes", int(287.6 * 1024 ** 2), "warn", UNCONFIRMED,
     "third-party guides: the iOS app takes about 287.6 MB; the web upload more"),
    ("tiktok", "audio_codecs", ("aac",), "warn", UNCONFIRMED, "no official page names an audio codec; guides say AAC"),
    ("shorts", "max_duration_s", 180, "fail", U_YT_SHORTS, "longer is filed as a long video, not a Short"),
    ("shorts", "vertical_or_square", True, "fail", U_YT_SHORTS, "a wider frame is filed as a long video"),
    ("shorts", "containers", ("mp4",), "warn", U_YT_ENC, "recommended: MP4"),
    ("shorts", "video_codecs", ("h264",), "warn", U_YT_ENC, "recommended: H.264"),
    ("shorts", "fps_list", (24, 25, 30, 48, 50, 60), "warn", U_YT_ENC, "common rates; upload at the recorded rate"),
    ("shorts", "audio_codecs", ("aac", "opus"), "warn", U_YT_ENC, "AAC-LC or Opus"),
    ("shorts", "audio_rate", 48000, "warn", U_YT_ENC, "48 kHz"),
    ("shorts", "max_bytes", 256 * GB, "fail", U_YT_SIZE, "256 GB or 12 h"),
    # every platform: no platform page states these; conventions from the two source repos
    ("*", "audio_present", True, "warn", UNCONFIRMED, "a silent upload is rarely meant"),
    ("*", "lufs_range", (-20.0, -9.0), "warn", UNCONFIRMED, "-14 LUFS is where platforms meet (XuHo, vargHQ convention)"),
    ("*", "true_peak_dbtp", -1.0, "warn", UNCONFIRMED, "EBU R128 ceiling; no platform page states it"),
    ("*", "av_gap_s", 0.25, "warn", UNCONFIRMED, "audio and video lengths apart (vargHQ fixtures)"),
]
PLATFORMS = ("reels", "tiktok", "shorts")


# ---------------------------------------------------------------- helpers
class CheckError(Exception):
    """The check could not run on this input; reported as status "error", exit 2."""


DECODE_MIN_SHARE = 0.9    # fewer decoded frames than this share of duration x fps is a decode failure


def run(cmd, **kw):
    return subprocess.run(cmd, check=True, capture_output=True, **kw)


def _tail(text, n=300):
    if isinstance(text, bytes):
        text = text.decode("utf-8", "replace")
    return " ".join((text or "").strip().split())[-n:]


def result(check, status, summary, **extra):
    return {"check": check, "status": status, "summary": summary, **extra}


def frac(s):
    try:
        n, d = (int(x) for x in str(s).split("/"))
        return n / d if d else 0.0
    except ValueError:
        return 0.0


_PROBES = {}


def container_of(fmt, v, a):
    """The real container, from ffprobe, not the file name. ffprobe names the ISO
    family "mov,mp4,m4a,3gp,3g2,mj2" and Matroska "matroska,webm", so the brand
    and the codecs settle which one."""
    names = fmt.get("format_name", "").split(",")
    if "mp4" in names or "mov" in names:
        return "mov" if fmt.get("tags", {}).get("major_brand", "").strip() == "qt" else "mp4"
    if "matroska" in names or "webm" in names:
        webm = v["codec_name"] in ("vp8", "vp9", "av1") and (a is None or a["codec_name"] in ("opus", "vorbis"))
        return "webm" if webm else "mkv"
    return names[0] or "unknown"


def probe(video):
    """ffprobe facts, rotation-aware (XuHo delivery-check.mjs probeFile)."""
    key = str(video)
    if key in _PROBES:
        return _PROBES[key]
    p = subprocess.run(["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", key],
                       capture_output=True, text=True)
    if p.returncode:
        raise CheckError(f"ffprobe cannot read {Path(key).name}: {_tail(p.stderr)}")
    j = json.loads(p.stdout)
    v = next((s for s in j.get("streams", []) if s["codec_type"] == "video"), None)
    if v is None:
        raise CheckError(f"no video stream in {Path(key).name}")
    a = next((s for s in j["streams"] if s["codec_type"] == "audio"), None)
    rot = v.get("tags", {}).get("rotate") or next(
        (sd.get("rotation") for sd in v.get("side_data_list", []) if "rotation" in sd), 0)
    turned = abs(int(float(rot or 0))) % 180 == 90
    avg, r = v.get("avg_frame_rate", "0/0"), v.get("r_frame_rate", "0/0")
    rate = avg if frac(avg) > 0 else r
    if frac(rate) <= 0:
        raise CheckError(f"{Path(key).name} reports no frame rate")
    fmt = j["format"]
    info = {
        "width": v["height"] if turned else v["width"], "height": v["width"] if turned else v["height"],
        "fps": frac(rate), "fps_fraction": rate, "r_fps": frac(r), "avg_fps": frac(avg),
        "video_codec": v["codec_name"], "pix_fmt": v.get("pix_fmt"),
        "duration": float(fmt.get("duration") or v.get("duration") or 0),
        "video_duration": float(v.get("duration") or fmt.get("duration") or 0),
        "bytes": int(fmt.get("size") or Path(key).stat().st_size),
        "kbps": (int(fmt["bit_rate"]) / 1000) if fmt.get("bit_rate") else None,
        "container": container_of(fmt, v, a), "format_name": fmt.get("format_name", ""),
        "audio": None if a is None else {
            "codec": a["codec_name"], "sample_rate": int(a.get("sample_rate") or 0),
            "channels": a.get("channels"), "kbps": (int(a["bit_rate"]) / 1000) if a.get("bit_rate") else None,
            "duration": float(a.get("duration") or 0)},
    }
    _PROBES[key] = info
    return info


def loudness(video):
    """Integrated LUFS and true peak via loudnorm, as breakdown.py reads them."""
    err = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(video), "-vn", "-af",
                          "loudnorm=print_format=json", "-f", "null", "-"], capture_output=True, text=True).stderr
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", err, re.S)
    if not m:
        return None
    j = json.loads(m.group(0))

    def num(k):
        x = float(j[k])
        return x if np.isfinite(x) else None
    i = num("input_i")
    # digital silence measures -inf; loudnorm's absolute gate sits at -70 LUFS
    return {"integrated_lufs": i, "true_peak_dbtp": num("input_tp"), "silent": i is None or i <= -70.0}


# ---------------------------------------------------------------- one decode pass
# sRGB to linear, WCAG 2.2 "relative luminance" (0.04045 since May 2021).
_C = np.arange(256, dtype=np.float32) / 255.0
LIN = np.where(_C <= 0.04045, _C / 12.92, ((_C + 0.055) / 1.055) ** 2.4).astype(np.float32)
D65_U, D65_V = 0.1978, 0.4683
_TRACES = {}


def trace(video):
    """Decode every frame once at SIDExSIDE. Keeps per-cell flash transitions and
    per-frame grey statistics; the flash state machine runs as frames stream in."""
    key = str(video)
    if key not in _TRACES:
        try:
            _TRACES[key] = _trace(video)
        except CheckError as e:
            _TRACES[key] = e          # every check that needs the frames reports the same error
    if isinstance(_TRACES[key], CheckError):
        raise _TRACES[key]
    return _TRACES[key]


def _trace(video):
    key = str(video)
    info = probe(video)
    cmd = ["ffmpeg", "-v", "error", "-i", key, "-map", "0:v:0", "-vf",
           f"fps={info['fps_fraction']},scale={SIDE}:{SIDE}:flags=area,format=rgb24", "-f", "rawvideo", "-"]
    errfile = tempfile.TemporaryFile()   # a file, not a pipe: a chatty decoder cannot block the read loop
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=errfile)
    size, c = SIDE * SIDE * 3, SIDE // GRID
    g8 = SIDE // 8
    gen_t, red_t, luma, std, p99, mad, cmax, skip2, cell_l = [], [], [], [], [], [], [], [], []
    prev = prev2 = None
    while True:
        buf = proc.stdout.read(size)
        if len(buf) < size:
            break
        f = np.frombuffer(buf, np.uint8).reshape(SIDE, SIDE, 3)
        cells = LIN[f].reshape(GRID, c, GRID, c, 3).mean(axis=(1, 3)).reshape(-1, 3)
        R, G, B = cells[:, 0], cells[:, 1], cells[:, 2]
        L = 0.2126 * R + 0.7152 * G + 0.0722 * B
        X = 0.4124 * R + 0.3576 * G + 0.1805 * B
        Z = 0.0193 * R + 0.1192 * G + 0.9505 * B
        den = X + 15 * L + 3 * Z
        ok = den > 1e-6
        u = np.where(ok, 4 * X / np.where(ok, den, 1), D65_U)   # black has no hue: call it white's
        v = np.where(ok, 9 * L / np.where(ok, den, 1), D65_V)
        s = R + G + B
        red = np.where(s > 1e-6, R / np.where(s > 1e-6, s, 1), 0) >= RED_RATIO
        if not cell_l:
            g_ref, g_dir = L.copy(), np.zeros(L.shape, np.int8)
            r_u, r_v, r_red, r_dir = u.copy(), v.copy(), red.copy(), np.zeros(L.shape, np.int8)
            gen_t.append(np.zeros(L.shape, bool))
            red_t.append(np.zeros(L.shape, bool))
        else:
            # general flash: vargHQ mj_frames.py transition counter, per cell instead of whole frame
            ch = L - g_ref
            big = (np.abs(ch) >= FLASH_DELTA) & (np.minimum(L, g_ref) < FLASH_DARK_MAX)
            d = np.sign(ch).astype(np.int8)
            gen_t.append(big & (d != g_dir))
            ext = ~big & (((g_dir > 0) & (L > g_ref)) | ((g_dir < 0) & (L < g_ref)))
            g_dir = np.where(big, d, g_dir)
            g_ref = np.where(big | ext, L, g_ref)
            # red flash: WCAG note 3, to or from saturated red with a u'v' jump over 0.2
            rt = (np.hypot(u - r_u, v - r_v) > RED_UV) & (red | r_red)
            rd = np.where(red, 1, -1).astype(np.int8)
            red_t.append(rt & (rd != r_dir))
            r_dir = np.where(rt, rd, r_dir)
            r_u, r_v, r_red = np.where(rt, u, r_u), np.where(rt, v, r_v), np.where(rt, red, r_red)
        cell_l.append(L.mean())
        g = f.astype(np.float32) @ np.array([0.299, 0.587, 0.114], np.float32)
        luma.append(float(g.mean()))
        std.append(float(g.std()))
        p99.append(float(np.percentile(g, 99)))
        if prev is None:
            mad.append(0.0), cmax.append(0.0), skip2.append(0.0)
        else:
            dd = np.abs(g - prev)
            mad.append(float(dd.mean()))
            cmax.append(float(dd.reshape(8, g8, 8, g8).mean(axis=(1, 3)).max()))
            skip2.append(float(np.abs(g - prev2).mean()) if prev2 is not None else 0.0)
        prev2, prev = prev, g
    proc.stdout.close()
    rc = proc.wait()
    errfile.seek(0)
    err = errfile.read().decode("utf-8", "replace")
    errfile.close()
    n = len(luma)
    lines = [ln for ln in err.splitlines() if ln.strip()]
    expected = info["video_duration"] * info["fps"]
    name = Path(key).name
    if rc:
        raise CheckError(f"ffmpeg could not decode {name} (exit {rc}): {_tail(err)}")
    if n == 0:
        raise CheckError(f"no frame of {name} decoded: {_tail(err) or 'empty output'}")
    if expected >= 2 and n < DECODE_MIN_SHARE * expected:
        raise CheckError(f"decoded {n} of about {expected:.0f} frames of {name}: {_tail(err) or 'stream ends early'}")
    if lines:
        # ffmpeg conceals damaged frames and the fps filter pads gaps, so the count alone can look whole
        raise CheckError(f"{len(lines)} decode error line(s) in {name}; the frames measured would be "
                         f"concealment, not the picture: {_tail(lines[0], 200)}")
    tr = {"fps": info["fps"], "n": n, "gen": np.array(gen_t), "red": np.array(red_t),
          "luma": np.array(luma), "std": np.array(std), "p99": np.array(p99), "mad": np.array(mad),
          "cmax": np.array(cmax), "skip2": np.array(skip2)}
    return tr


def runs(mask):
    out, i, n = [], 0, len(mask)
    while i < n:
        if mask[i]:
            j = i
            while j + 1 < n and mask[j + 1]:
                j += 1
            out.append((i, j))
            i = j + 1
        else:
            i += 1
    return out


# ---------------------------------------------------------------- checks
def flash_area(trans, fps):
    """Per frame: worst flashes/s in any cell of a 10-degree field whose flashing share is over 25%."""
    n = len(trans)
    if n == 0:
        return np.zeros(0, bool), np.zeros(0), 0.0
    w = max(1, int(round(fps)))
    cs = np.concatenate([np.zeros((1, trans.shape[1]), np.int32), np.cumsum(trans, axis=0, dtype=np.int32)])
    idx = np.arange(n)
    flashes = (cs[idx + 1] - cs[np.maximum(0, idx + 1 - w)]) / 2.0          # per cell, the second ending here
    over = (flashes > FLASH_MAX_PER_S).reshape(n, GRID, GRID).astype(np.int32)
    s = np.zeros((n, GRID + 1, GRID + 1), np.int32)
    s[:, 1:, 1:] = over.cumsum(1).cumsum(2)
    k = FIELD
    field = s[:, k:, k:] - s[:, :-k, k:] - s[:, k:, :-k] + s[:, :-k, :-k]
    share = field.max(axis=(1, 2)) / float(k * k)
    bad = share > FIELD_AREA
    return bad, flashes.max(axis=1), float(share.max())


def check_flash(video):
    tr = trace(video)
    fps, events, worst = tr["fps"], [], {}
    for kind in ("gen", "red"):
        bad, peak, share = flash_area(tr[kind], fps)
        name = "general" if kind == "gen" else "red"
        worst[name] = {"max_flashes_per_s": round(float(peak.max()) if len(peak) else 0.0, 1),
                       "largest_field_share": round(share, 3)}
        for a, b in runs(bad):
            events.append({"kind": name, "t": round(max(0.0, (a + 1) / fps - 1.0), 2), "t_end": round((b + 1) / fps, 2),
                           "flashes_per_s": round(float(peak[a:b + 1].max()), 1)})
    status = "fail" if events else "pass"
    if events:
        e = max(events, key=lambda x: x["flashes_per_s"])
        summary = (f"{len(events)} stretch(es) over WCAG 2.3.1; worst {e['flashes_per_s']} {e['kind']} flashes/s "
                   f"at {e['t']:.2f}-{e['t_end']:.2f} s over >25% of a 10-degree field")
    else:
        summary = (f"under WCAG 2.3.1: at most {worst['general']['max_flashes_per_s']} general and "
                   f"{worst['red']['max_flashes_per_s']} red flashes/s in any cell, area rule not met")
    return result("flash", status, summary, events=events[:20], measured=worst,
                  thresholds={"flashes_per_s": f"> {FLASH_MAX_PER_S}", "luminance_delta": FLASH_DELTA,
                              "darker_below": FLASH_DARK_MAX, "red": f"R/(R+G+B) >= {RED_RATIO}, u'v' > {RED_UV}",
                              "area": f"> {FIELD_AREA:.0%} of a {FIELD}/{GRID}-side field"},
                  source="WCAG 2.2 SC 2.3.1, https://www.w3.org/TR/WCAG22/#dfn-general-flash-and-red-flash-thresholds")


def check_blank(video):
    """Luma range of sampled frames (XuHo blank-check.mjs), run over the whole video."""
    probe(video)          # an unreadable file says so plainly before ffmpeg is run on it
    out = run(["ffmpeg", "-v", "error", "-i", str(video), "-map", "0:v:0", "-vf",
               f"fps={BLANK_RATE},signalstats,metadata=print:file=-", "-f", "null", "-"], text=True).stdout
    ranges, ymin = [], None
    for line in out.splitlines():
        m = re.search(r"signalstats\.Y(MIN|MAX)=([\d.]+)", line)
        if m and m.group(1) == "MIN":
            ymin = float(m.group(2))
        elif m and ymin is not None:
            ranges.append(float(m.group(2)) - ymin)
            ymin = None
    if not ranges:
        raise CheckError(f"signalstats returned no frame of {Path(video).name}")
    flat = np.array(ranges) < FLAT_RANGE
    n, events, edges = len(flat), [], []
    for a, b in runs(flat):
        dur = (b - a + 1) / BLANK_RATE
        e = {"t": round(a / BLANK_RATE, 2), "t_end": round((b + 1) / BLANK_RATE, 2), "duration_s": dur,
             "luma_range": round(float(max(ranges[a:b + 1])), 1)}
        at_edge = a == 0 or b == n - 1
        whole = (b - a + 1) == n          # a clip flat from end to end fails at any length, even under 1 s
        if whole or (dur >= BLANK_MIN_S and not (at_edge and dur <= BLANK_EDGE_S)):
            events.append(e)
        else:
            edges.append(e)
    if events:
        summary = (f"{len(events)} flat stretch(es), {sum(e['duration_s'] for e in events):.2f} s in all, "
                   f"first at {events[0]['t']:.2f} s: nothing drawn")
    else:
        summary = f"no flat stretch of {BLANK_MIN_S} s or more ({len(edges)} short or edge fade(s) left alone)"
    return result("blank", "fail" if events else "pass", summary, events=events[:20], allowed=edges[:10],
                  thresholds={"luma_range_under": FLAT_RANGE, "min_s": BLANK_MIN_S, "edge_fade_s": BLANK_EDGE_S},
                  source="XuHo-IT/Content-Agent-Kit scripts/video/lib/blank-check.mjs (FLAT_RANGE 20)")


def check_frames(video):
    """Black seam frames and one-frame glitches (vargHQ mj_frames.py)."""
    tr = trace(video)
    n, fps = tr["n"], tr["fps"]
    if n < 3:
        return [result("black_seam", "skip", "fewer than 3 frames"), result("glitch", "skip", "fewer than 3 frames")]
    L, M, C, S2 = tr["luma"], tr["mad"], tr["cmax"], tr["skip2"]
    black = (L < BLACK_LUMA) & (tr["std"] < BLACK_STD) & (tr["p99"] < BLACK_P99)
    seams = []
    for a, b in runs(black):
        dur = (b - a + 1) / fps
        abrupt = (L[a - 1] if a > 0 else 0) > 2 * BLACK_LUMA or (L[b + 1] if b + 1 < n else 0) > 2 * BLACK_LUMA
        if a > 1 and b < n - 2 and dur <= BLACK_MAX_S and abrupt:
            seams.append({"t": round(a / fps, 3), "frames": int(b - a + 1)})
    glitches, last = [], -10
    for i in range(1, n - 1):
        d_in, d_out, through = M[i], M[i + 1], S2[i + 1]
        lo, hi = max(1, i - 12), min(n, i + 13)
        local, local_cell = float(np.median(M[lo:hi])), float(np.median(C[lo:hi]))
        whole = min(d_in, d_out) > max(GLITCH_MIN_MAD, 4 * local) and through < GLITCH_RETURN * min(d_in, d_out)
        part = (min(C[i], C[i + 1]) > max(GLITCH_MIN_CELL, 4 * local_cell)
                and through < 0.6 * max(d_in, d_out) and min(d_in, d_out) > 1.5 * through)
        if (whole or part) and i - last > 1:
            glitches.append({"t": round(i / fps, 3), "frame": i, "jump_in": round(float(d_in), 1),
                             "jump_out": round(float(d_out), 1), "neighbours_differ": round(float(through), 1)})
        if whole or part:
            last = i
    src = "vargHQ/skills media-judge/scripts/mj_frames.py (thresholds calibrated on its fixtures)"
    return [
        result("black_seam", "fail" if seams else "pass",
               f"{len(seams)} black run(s) of <= {BLACK_MAX_S} s cut into the picture" + (
                   f", first at {seams[0]['t']:.3f} s" if seams else ""),
               events=seams[:20], source=src,
               thresholds={"luma": BLACK_LUMA, "std": BLACK_STD, "p99": BLACK_P99, "max_s": BLACK_MAX_S}),
        result("glitch", "warn" if glitches else "pass",
               f"{len(glitches)} frame(s) unlike both neighbours, which match each other" + (
                   f", first at {glitches[0]['t']:.3f} s (a deliberate one-frame flash also reads this way)"
                   if glitches else ""),
               events=glitches[:20], source=src,
               thresholds={"min_mad": GLITCH_MIN_MAD, "min_cell": GLITCH_MIN_CELL, "return": GLITCH_RETURN}),
    ]


def has_libvmaf():
    out = subprocess.run(["ffmpeg", "-hide_banner", "-filters"], capture_output=True, text=True).stdout
    return re.search(r"\blibvmaf\b", out) is not None


def check_banding(video):
    """CAMBI through ffmpeg's libvmaf, the call vargHQ mj_compress.py makes, on the file itself."""
    if not has_libvmaf():
        return result("banding", "skip", "this ffmpeg has no libvmaf filter, so CAMBI cannot run")
    info, tr = probe(video), trace(video)
    sub = max(1, int(round(info["fps"] / 2)))
    with tempfile.TemporaryDirectory() as tmp:
        log = Path(tmp) / "cambi.json"
        p = subprocess.run(["ffmpeg", "-v", "error", "-i", str(video), "-i", str(video), "-lavfi",
                            f"[0:v][1:v]libvmaf=feature=name=cambi:log_fmt=json:log_path={log}:n_subsample={sub}:n_threads=4",
                            "-f", "null", "-"], capture_output=True, text=True)
        if p.returncode or not log.exists():
            raise CheckError("libvmaf/CAMBI did not run: " + _tail(p.stderr, 200))
        frames = json.loads(log.read_text())["frames"]
    events, worst = [], 0.0
    for fr in frames:
        c = fr["metrics"].get("cambi")
        if c is None:
            continue
        i = int(fr["frameNum"])
        worst = max(worst, c)
        lum = float(tr["luma"][min(i, tr["n"] - 1)]) if tr["n"] else 255.0
        dark = lum < DARK_LUMA
        if c >= CAMBI_VISIBLE * (1 if dark else CAMBI_BRIGHT_FACTOR):
            events.append({"t": round(i / info["fps"], 2), "cambi": round(c, 2), "dark": dark})
    summary = (f"{len(events)} sampled frame(s) with visible banding, worst CAMBI {worst:.1f}" if events
               else f"worst CAMBI {worst:.1f}, under {CAMBI_VISIBLE} (dark) / {CAMBI_VISIBLE * CAMBI_BRIGHT_FACTOR} (bright)")
    if events:
        summary += "; it gets worse after the platform re-encodes: add grain or lift the blacks"
    return result("banding", "warn" if events else "pass", summary, events=events[:20],
                  thresholds={"dark": CAMBI_VISIBLE, "bright": CAMBI_VISIBLE * CAMBI_BRIGHT_FACTOR, "dark_luma": DARK_LUMA},
                  source="Netflix vmaf resource/doc/cambi.md; dark/bright split from vargHQ mj_compress.py")


def _ratio_name(r):
    for name, x in (("9:16", 9 / 16), ("16:9", 16 / 9), ("1:1", 1.0), ("4:5", 0.8)):
        if abs(r - x) <= 0.02:
            return name
    return f"{r:.3f}"


def check_delivery(video, platforms):
    info = probe(video)
    a = info["audio"]
    loud = loudness(video) if a else None
    out = []
    for plat in platforms:
        findings = []

        def hit(level, src, msg, note):
            lvl = "warn" if src == UNCONFIRMED and level == "fail" else level
            findings.append({"level": lvl, "message": msg, "note": note,
                             "source": "source: unconfirmed" if src == UNCONFIRMED else f"{src} (checked {CHECKED})"})
        w, h, dur, r = info["width"], info["height"], info["duration"], info["width"] / info["height"]
        for p, limit, val, level, src, note in DELIVERY:
            if p not in (plat, "*"):
                continue
            if limit == "max_duration_s" and dur > val + 0.05:
                hit(level, src, f"{dur:.1f} s, at most {val} s", note)
            elif limit == "recommend_max_s" and dur > val + 0.05:
                hit(level, src, f"{dur:.1f} s, over {val} s", note)
            elif limit == "containers" and info["container"] not in val:
                hit(level, src, f"container {info['container']} (ffprobe: {info['format_name']}), needs {'/'.join(val)}", note)
            elif limit == "video_codecs" and info["video_codec"] not in val:
                hit(level, src, f"video codec {info['video_codec']}, expected {'/'.join(val)}", note)
            elif limit == "constant_fps" and info["r_fps"] and info["avg_fps"] and abs(info["r_fps"] - info["avg_fps"]) > 0.01 * info["r_fps"]:
                hit(level, src, f"variable frame rate (nominal {info['r_fps']:.3f}, average {info['avg_fps']:.3f})", note)
            elif limit == "aspect" and not any(abs(r - x) <= 0.02 for x in val):
                hit(level, src, f"ratio {_ratio_name(r)}, {' or '.join(_ratio_name(x) for x in val)} fills the screen", note)
            elif limit == "max_bytes" and info["bytes"] > val:
                hit(level, src, f"{info['bytes'] / 1024 ** 2:.1f} MB, at most {val / 1024 ** 2:.0f} MB", note)
            elif limit == "app_max_bytes" and info["bytes"] > val:
                hit(level, src, f"{info['bytes'] / 1024 ** 2:.1f} MB, over {val / 1024 ** 2:.1f} MB", note)
            elif limit == "fps_range" and not (val[0] - 0.5 <= info["fps"] <= val[1] + 0.5):
                hit(level, src, f"{info['fps']:.2f} fps, needs {val[0]}-{val[1]}", note)
            elif limit == "fps_list" and not any(abs(info["fps"] * k - x) <= 0.05 * x / 30 + 0.03
                                                 for x in val for k in (1, 1.001)):
                hit(level, src, f"{info['fps']:.3f} fps, not one of {', '.join(map(str, val))}", note)
            elif limit == "dim_range" and not (val[0] <= min(w, h) and max(w, h) <= val[1]):
                hit(level, src, f"{w}x{h}, each side must be {val[0]}-{val[1]} px", note)
            elif limit == "min_res" and (min(w, h) < min(val) or max(w, h) < max(val)):
                hit(level, src, f"{w}x{h}, under {val[0]}x{val[1]}", note)
            elif limit == "min_kbps" and info["kbps"] and info["kbps"] < val:
                hit(level, src, f"{info['kbps']:.0f} kbps, under {val}", note)
            elif limit == "vertical_or_square" and w > h:
                hit(level, src, f"{w}x{h} is landscape; a Short is square or vertical", note)
            elif limit == "audio_present" and not a:
                hit(level, src, "no audio track", note)
            elif limit == "audio_present" and loud and loud["silent"]:
                hit(level, src, "audio track is silent (integrated loudness -inf or under -70 LUFS)", note)
            elif limit == "note":
                hit(level, src, val, note)
            elif not a:
                continue
            elif limit == "audio_codecs" and a["codec"] not in val:
                hit(level, src, f"audio {a['codec']}, expected {'/'.join(val)}", note)
            elif limit == "audio_channels" and a["channels"] != val:
                hit(level, src, f"{a['channels']} audio channel(s), expected {val}", note)
            elif limit == "audio_min_kbps" and a["kbps"] and a["kbps"] < val:
                hit(level, src, f"audio {a['kbps']:.0f} kbps, under {val}", note)
            elif limit == "audio_rate" and a["sample_rate"] != val:
                hit(level, src, f"audio {a['sample_rate']} Hz, expected {val}", note)
            elif limit == "lufs_range" and loud and loud["integrated_lufs"] is not None and not (val[0] <= loud["integrated_lufs"] <= val[1]):
                hit(level, src, f"{loud['integrated_lufs']:.1f} LUFS, outside {val[0]} to {val[1]}", note)
            elif limit == "true_peak_dbtp" and loud and loud["true_peak_dbtp"] is not None and loud["true_peak_dbtp"] > val:
                hit(level, src, f"true peak {loud['true_peak_dbtp']:.1f} dBTP, over {val}", note)
            elif limit == "av_gap_s" and a["duration"] and info["video_duration"] and abs(a["duration"] - info["video_duration"]) > val:
                hit(level, src, f"audio {a['duration']:.2f} s against video {info['video_duration']:.2f} s", note)
        fails = [f for f in findings if f["level"] == "fail"]
        warns = [f for f in findings if f["level"] == "warn"]
        status = "fail" if fails else "warn" if warns else "pass"
        summary = (f"{len(fails)} failure(s), {len(warns)} warning(s): "
                   + "; ".join(f["message"] for f in (fails + warns)[:4])) if fails or warns else "within every limit checked"
        out.append(result(f"delivery:{plat}", status, summary, findings=findings,
                          file={k: info[k] for k in ("width", "height", "fps", "video_codec", "container", "bytes", "duration")},
                          loudness=loud))
    return out


# ---------------------------------------------------------------- captions
def _seconds(x):
    """A finite number of seconds, or None (null, "0:01", NaN and booleans are not times)."""
    if isinstance(x, bool):
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if np.isfinite(v) else None


def _first(it, *keys):
    return next((it[k] for k in keys if it.get(k) is not None), None)


def load_captions(path):
    """Return (items, reason, dropped): items are {id, text, start, end, pass}; reason is set when
    nothing can be judged; dropped lists the texts whose times could not be read."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("segments") or data.get("captions") or data.get("texts") or []
    if not isinstance(data, list):
        raise CheckError(f"{Path(path).name}: expected a list of captions or WhisperX segments")
    items, dropped, words = [], [], 0
    for k, it in enumerate(data):
        if not isinstance(it, dict):
            dropped.append({"index": k, "why": "not an object"})
            continue
        if "text" not in it and "word" in it:
            words += 1
            continue
        text = str(it.get("text") or "").strip()
        if not text:
            continue
        start, end = _seconds(_first(it, "start", "t0")), _seconds(_first(it, "end", "t1"))
        dur = _seconds(it.get("duration"))
        if end is None and start is not None and dur is not None:
            end = start + dur
        why = ("no readable start" if start is None else "no readable end or duration" if end is None
               else "ends before it starts" if end < start else None)
        if why:
            dropped.append({"index": k, "id": it.get("id"), "why": why, "text": text[:40]})
            continue
        items.append({"text": text, "start": start, "end": end, "pass": bool(it.get("pass")),
                      "id": None if it.get("id") is None else str(it["id"]), "index": k})
    if not items and words and not dropped:
        return [], "a word-level list: one word on screen is not a text to time; pass the sentence-level JSON", []
    if not items and dropped:
        raise CheckError(f"no caption in {Path(path).name} has readable times ({len(dropped)} dropped, "
                         f"first: {dropped[0]['why']})")
    if not items:
        return [], "no {text, start, end} items found", []
    return items, None, dropped


def _is_cjk(ch):
    n = unicodedata.name(ch, "")
    return n.startswith(("CJK", "HIRAGANA", "KATAKANA", "HANGUL"))


def need_seconds(text):
    """lemo-opuscar readcheck.mjs: CJK / 4.5 + other / 15 + 1.5 s, at least 1.5 s; whitespace not counted."""
    cjk = sum(1 for ch in text if not ch.isspace() and _is_cjk(ch))
    other = sum(1 for ch in text if not ch.isspace() and not _is_cjk(ch))
    return max(READ_MIN, cjk / CJK_CPS + other / LATIN_CPS + READ_PAD)


def check_reading(captions, video=None):
    items, reason, dropped = load_captions(captions)
    if reason:
        return result("reading", "skip", reason)
    items.sort(key=lambda x: x["start"])
    # One piece of text is its id plus its text (lemo readcheck.mjs): the same text under the same
    # id (or both without an id) shown again within 50 ms is one piece; a new id is a new piece.
    merged = []
    for it in items:
        if (merged and merged[-1]["id"] == it["id"] and merged[-1]["text"] == it["text"]
                and it["start"] - merged[-1]["end"] <= 0.05):
            merged[-1]["end"] = max(merged[-1]["end"], it["end"])
        else:
            merged.append(dict(it))
    end_cap = probe(video)["duration"] if video else None
    bad, rows = [], []
    for it in merged:
        shown = (min(it["end"], end_cap) if end_cap else it["end"]) - it["start"]
        need = need_seconds(it["text"])
        row = {"id": it["id"] if it["id"] is not None else f"#{it['index']}", "t": round(it["start"], 2),
               "chars": sum(1 for ch in it["text"] if not ch.isspace()),
               "need_s": round(need, 2), "shown_s": round(shown, 2), "text": it["text"][:40]}
        if it["pass"]:
            row["passing"] = True
        elif shown + 1e-6 < need:
            bad.append(row)
        rows.append(row)
    summary = (f"{len(bad)} of {len(rows)} timed text(s) leave before they can be read; first at {bad[0]['t']:.2f} s "
               f"({bad[0]['shown_s']} s shown, {bad[0]['need_s']} s needed)" if bad
               else f"all {len(rows)} timed text(s) stay long enough")
    if dropped:
        summary += (f"; {len(dropped)} item(s) not timed, their times unreadable "
                    f"(first: item {dropped[0]['index']}, {dropped[0]['why']})")
    status = "fail" if bad else "warn" if dropped else "pass"
    return result("reading", status, summary, events=bad[:30], dropped=dropped[:30],
                  thresholds={"latin_cps": LATIN_CPS, "cjk_cps": CJK_CPS, "pad_s": READ_PAD, "min_s": READ_MIN},
                  source="lemomo-ai/lemo-opuscar core/render/readcheck.mjs")


# ---------------------------------------------------------------- fonts
def _u16(b, o):
    return struct.unpack_from(">H", b, o)[0]


def _u32(b, o):
    return struct.unpack_from(">I", b, o)[0]


def _woff_to_tables(data):
    """WOFF 1.0: zlib-compressed tables. Returns {tag: bytes}."""
    n = _u16(data, 12)
    tables = {}
    for i in range(n):
        tag, off, comp, orig, _ = struct.unpack_from(">4sIIII", data, 44 + 20 * i)
        raw = data[off:off + comp]
        tables[tag] = zlib.decompress(raw) if comp < orig else raw
    return tables


def _sfnt_tables(data, index=0):
    if data[:4] == b"wOFF":
        return _woff_to_tables(data)
    base = _u32(data, 12 + 4 * index) if data[:4] == b"ttcf" else 0
    n = _u16(data, base + 4)
    tables = {}
    for i in range(n):
        tag, _, off, length = struct.unpack_from(">4sIII", data, base + 12 + 16 * i)
        tables[tag] = data[off:off + length]
    return tables


def _glyph(cmap, sub, cp):
    fmt = _u16(cmap, sub)
    if fmt == 4:
        if cp > 0xFFFF:
            return 0
        segs = _u16(cmap, sub + 6) // 2
        ends, starts = sub + 14, sub + 16 + 2 * segs
        deltas, ranges = sub + 16 + 4 * segs, sub + 16 + 6 * segs
        for i in range(segs):
            if cp <= _u16(cmap, ends + 2 * i):
                st = _u16(cmap, starts + 2 * i)
                if cp < st:
                    return 0
                ro = _u16(cmap, ranges + 2 * i)
                if ro == 0:
                    return (cp + _u16(cmap, deltas + 2 * i)) & 0xFFFF
                g = _u16(cmap, ranges + 2 * i + ro + 2 * (cp - st))
                return (g + _u16(cmap, deltas + 2 * i)) & 0xFFFF if g else 0
        return 0
    if fmt in (12, 13):
        for i in range(_u32(cmap, sub + 12)):
            s, e, g = struct.unpack_from(">III", cmap, sub + 16 + 12 * i)
            if s <= cp <= e:
                return g + (cp - s if fmt == 12 else 0)
        return 0
    if fmt == 0:
        return cmap[sub + 6 + cp] if cp < 256 else 0
    if fmt == 6:
        first, count = _u16(cmap, sub + 6), _u16(cmap, sub + 8)
        return _u16(cmap, sub + 10 + 2 * (cp - first)) if first <= cp < first + count else 0
    return 0


def covered_by_cmap(data, cps):
    """Code points in `cps` that the font's Unicode cmap subtables map to a real glyph."""
    cmap = _sfnt_tables(data).get(b"cmap")
    if not cmap:
        raise ValueError("no cmap table")
    subs = []
    for i in range(_u16(cmap, 2)):
        plat, enc, off = struct.unpack_from(">HHI", cmap, 4 + 8 * i)
        if plat == 0 or (plat == 3 and enc in (1, 10)):
            subs.append(off)
    return {cp for cp in cps if any(_glyph(cmap, s, cp) for s in subs)}


def covered_by_fcquery(path, cps):
    p = subprocess.run(["fc-query", "--format=%{charset}\n", str(path)], capture_output=True, text=True)
    out = p.stdout.split("\n")[0]
    if p.returncode or not out.strip():
        raise CheckError(f"fc-query cannot read {Path(path).name}: {_tail(p.stderr) or 'no charset'}")
    got = set()
    for part in out.split():
        a, _, b = part.partition("-")
        lo, hi = int(a, 16), int(b or a, 16)
        got |= {cp for cp in cps if lo <= cp <= hi}
    return got


def resolve_font(spec):
    """A file path, or a family name looked up in the local fontconfig (never the network)."""
    p = Path(spec)
    if p.is_file():
        return p, None
    if not shutil.which("fc-match"):
        raise CheckError(f"{spec} is not a file and fc-match is not on PATH")
    fam = run(["fc-match", "-f", "%{family}", spec], text=True).stdout
    path = run(["fc-match", "-f", "%{file}", spec], text=True).stdout
    if spec.lower() not in [x.strip().lower() for x in fam.split(",")]:
        return None, f"family {spec!r} is not installed; fontconfig would substitute {fam.split(',')[0]!r} ({path})"
    return Path(path), None


def check_fonts(font, texts):
    chars = sorted({ch for t in texts for ch in unicodedata.normalize("NFC", t) if not ch.isspace() and ch.isprintable()})
    if not chars:
        return result("fonts", "skip", "no text to check")
    path, err = resolve_font(font)
    if err:
        return result("fonts", "fail", err)
    data = path.read_bytes()
    cps = {ord(c) for c in chars}
    try:
        if data[:4] == b"wOF2":
            raise ValueError("WOFF2 needs brotli")
        got, how = covered_by_cmap(data, cps), "cmap"
    except (ValueError, struct.error, zlib.error, IndexError) as e:
        if not shutil.which("fc-query"):
            raise CheckError(f"cannot read {path.name} ({e}) and fc-query is not on PATH") from None
        got, how = covered_by_fcquery(path, cps), "fc-query"
    missing = [c for c in chars if ord(c) not in got]
    summary = (f"{path.name} has no glyph for {len(missing)} character(s): {''.join(missing)[:40]} "
               "(the renderer draws them from a fallback face)" if missing
               else f"{path.name} covers all {len(chars)} distinct characters")
    return result("fonts", "fail" if missing else "pass", summary, font=str(path), method=how,
                  missing=[f"U+{ord(c):04X} {c}" for c in missing],
                  source="idea from XuHo-IT/Content-Agent-Kit scripts/video/font-check.mjs; reads the font's own cmap")


# ---------------------------------------------------------------- report
ORDER = {"fail": 0, "error": 1, "warn": 2, "skip": 3, "pass": 4}


def verdict(results):
    """(ok, exit code, checks that ran): 1 on any fail, else 2 on any error or nothing checked, else 0."""
    checked = sum(r["status"] in ("pass", "warn", "fail") for r in results)
    if any(r["status"] == "fail" for r in results):
        return False, 1, checked
    if any(r["status"] == "error" for r in results) or checked == 0:
        return False, 2, checked
    return True, 0, checked


def print_report(results, as_json, target):
    ok, code, checked = verdict(results)
    if as_json:
        print(json.dumps({"target": target, "ok": ok, "checked": checked, "checks": results},
                         indent=2, ensure_ascii=False))
        return code
    for r in results:
        print(f"{r['status'].upper():<6}{r['check']:<17}{r['summary']}")
        for f in r.get("findings", []):
            print(f"        {f['level']:<5}{f['message']}  [{f['source']}]{'  ' + f['note'] if f['note'] else ''}")
    counts = {s: sum(r["status"] == s for r in results) for s in ORDER}
    print(f"render_qc: {counts['fail']} fail, {counts['error']} error, {counts['warn']} warn, "
          f"{counts['skip']} skipped, {counts['pass']} pass" + ("; nothing was checked" if not checked else ""))
    return code


def guarded(name, fn, *args):
    """Run one check; whatever stops it becomes an "error" result, so the other checks still run."""
    try:
        r = fn(*args)
        return r if isinstance(r, list) else [r]
    except CheckError as e:
        return [result(name, "error", str(e))]
    except subprocess.CalledProcessError as e:
        tool = Path(str(e.cmd[0])).name if e.cmd else "a tool"
        return [result(name, "error", f"{tool} exited {e.returncode}: {_tail(e.stderr) or 'no message'}")]
    except (OSError, ValueError, KeyError, IndexError, TypeError, struct.error, zlib.error) as e:
        return [result(name, "error", f"{type(e).__name__}: {e}")]


def run_checks(cmd, video, a):
    res = []
    platforms = [p.strip() for p in (a.platform or "").split(",") if p.strip()]
    for p in platforms:
        if p not in PLATFORMS:
            print(f"render_qc: unknown platform {p!r}; one of {', '.join(PLATFORMS)}", file=sys.stderr)
            sys.exit(2)
    if cmd in ("all", "flash"):
        res += guarded("flash", check_flash, video)
    if cmd in ("all", "blank"):
        res += guarded("blank", check_blank, video)
    if cmd in ("all", "frames"):
        res += guarded("frames", check_frames, video)
    if cmd in ("all", "banding"):
        res += guarded("banding", check_banding, video)
    if cmd in ("all", "delivery"):
        if platforms:
            res += guarded("delivery", check_delivery, video, platforms)
        else:
            res.append(result("delivery", "skip", "no --platform given"))
    if cmd in ("all", "reading"):
        res += (guarded("reading", check_reading, a.captions, video) if a.captions
                else [result("reading", "skip", "no --captions given")])
    if cmd in ("all", "fonts"):
        res += guarded("fonts", _fonts_from_args, a) if a.font else [result("fonts", "skip", "no --font given")]
    return res


def _fonts_from_args(a):
    texts = list(a.text or [])
    if a.captions:
        texts += [i["text"] for i in load_captions(a.captions)[0]]
    return check_fonts(a.font, texts)


# ---------------------------------------------------------------- self-test
def _tiny_font(cmap_cps):
    """A minimal sfnt with only a format-4 cmap mapping each code point to glyph 1."""
    segs = [(cp, cp) for cp in sorted(cmap_cps)] + [(0xFFFF, 0xFFFF)]
    n = len(segs)
    sub = struct.pack(">HHHHHHH", 4, 0, 0, 2 * n, 0, 0, 0)
    sub += b"".join(struct.pack(">H", e) for _, e in segs) + b"\0\0"
    sub += b"".join(struct.pack(">H", s) for s, _ in segs)
    sub += b"".join(struct.pack(">H", (1 - s) & 0xFFFF if s != 0xFFFF else 1) for s, _ in segs)
    sub += b"\0\0" * n
    sub = sub[:2] + struct.pack(">H", len(sub)) + sub[4:]
    cmap = struct.pack(">HHHHI", 0, 1, 3, 1, 12) + sub
    head = struct.pack(">IHHHH", 0x00010000, 1, 16, 0, 0)
    return head + struct.pack(">4sIII", b"cmap", 0, 12 + 16, len(cmap)) + cmap


def _woff(sfnt):
    """Wrap a one-table sfnt as WOFF 1.0 with the table compressed."""
    tag, _, off, length = struct.unpack_from(">4sIII", sfnt, 12)
    table = sfnt[off:off + length]
    comp = zlib.compress(table)
    hdr = struct.pack(">4sIIHHIHHIIIII", b"wOFF", 0x00010000, 44 + 20 + len(comp), 1, 0, len(sfnt), 0, 0, 0, 0, 0, 0, 0)
    return hdr + struct.pack(">4sIIII", tag, 64, len(comp), len(table), 0) + comp


def self_test():
    """Build tiny clips with ffmpeg lavfi and check each defect is caught and the clean clip passes."""
    for tool in ("ffmpeg", "ffprobe"):
        if not shutil.which(tool):
            print(f"self-test skipped: {tool} not on PATH, and without it the script does nothing")
            return 0
    checks = 0
    with tempfile.TemporaryDirectory() as tmp:
        t = Path(tmp)

        def make(name, src, extra=(), size="360x640", dur=3, audio="sine=f=440:d={dur}:sample_rate=48000"):
            out = t / f"{name}.mp4"
            cmd = ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", src.format(size=size, dur=dur)]
            if audio:
                cmd += ["-f", "lavfi", "-i", audio.format(dur=dur), "-ac", "2", "-c:a", "aac", "-b:a", "128k"]
            run(cmd + ["-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p"] + list(extra) + ["-t", str(dur), str(out)])
            return out

        clean = make("clean", "testsrc2=s={size}:r=30:d={dur}")
        flashing = make("flash", "color=c=gray:s={size}:r=30:d={dur},format=gray,geq=lum='if(mod(floor(N/3),2),235,16)'")
        slow = make("slow", "color=c=gray:s={size}:r=30:d={dur},format=gray,geq=lum='if(mod(floor(N/15),2),235,16)'")
        small = make("small", "testsrc2=s={size}:r=30:d={dur}",
                     ["-vf", "drawbox=x=0:y=0:w=iw/12:h=ih/12:c=white:t=fill:enable='mod(floor(n/3),2)'"])
        red = make("red", "color=c=gray:s={size}:r=30:d={dur},format=gbrp,"
                          "geq=r='if(mod(floor(N/3),2),255,127)':g='if(mod(floor(N/3),2),0,127)':b='if(mod(floor(N/3),2),0,127)'")
        blank = make("blank", "color=c=black:s={size}:r=30:d={dur}")
        mid_blank = make("midblank", "testsrc2=s={size}:r=30:d=4",
                         ["-vf", "drawbox=c=black:t=fill:enable='between(t,1.5,3)'"], dur=4)
        seam = make("seam", "testsrc2=s={size}:r=30:d={dur}", ["-vf", "drawbox=c=black:t=fill:enable='between(n,40,41)'"])
        glitch = make("glitch", "testsrc2=s={size}:r=30:d={dur}", ["-vf", "negate=enable='eq(n,45)'"])
        land = make("land", "testsrc2=s={size}:r=30:d={dur}", size="640x360")

        f = check_flash(flashing)
        assert f["status"] == "fail" and f["measured"]["general"]["max_flashes_per_s"] >= 4, f
        r = check_flash(red)
        assert r["status"] == "fail" and any(e["kind"] == "red" for e in r["events"]), r
        assert r["measured"]["general"]["max_flashes_per_s"] <= FLASH_MAX_PER_S, ("red clip read as luminance flash", r)
        for clip, why in ((clean, "clean"), (slow, "1 flash/s"), (small, "under 25% of the field")):
            c = check_flash(clip)
            assert c["status"] == "pass", (why, c)
        checks += 5

        assert check_blank(blank)["status"] == "fail"
        mb = check_blank(mid_blank)
        assert mb["status"] == "fail" and 1.4 <= mb["events"][0]["t"] <= 1.6, mb
        assert check_blank(clean)["status"] == "pass"
        checks += 3

        bs, gl = check_frames(seam)
        assert bs["status"] == "fail" and abs(bs["events"][0]["t"] - 40 / 30) < 0.05, bs
        bs, gl = check_frames(glitch)
        assert gl["status"] == "warn" and abs(gl["events"][0]["t"] - 45 / 30) < 0.05, gl
        assert bs["status"] == "pass", bs
        assert [x["status"] for x in check_frames(clean)] == ["pass", "pass"]
        checks += 3

        if has_libvmaf():
            # a dark ramp one 8-bit level per 40 px: CAMBI about 13 (lavfi gradients is seeded at random)
            banded = make("band", "color=c=black:s={size}:r=25:d={dur},format=gray,geq=lum='16+16*Y/H'",
                          ["-crf", "18"], dur=1)
            b = check_banding(banded)
            assert b["status"] == "warn", b
            assert check_banding(clean)["status"] == "pass"
            checks += 2
        else:
            print("self-test: banding not tested, this ffmpeg has no libvmaf")

        d = {x["check"]: x for x in check_delivery(clean, ["reels", "tiktok", "shorts"])}
        assert all(x["status"] != "fail" for x in d.values()), d
        dl = {x["check"]: x for x in check_delivery(land, ["shorts", "tiktok"])}
        assert dl["delivery:shorts"]["status"] == "fail", dl
        assert any("ratio" in m["message"] for m in dl["delivery:tiktok"]["findings"]), dl
        tiny = make("tiny", "testsrc2=s={size}:r=30:d={dur}", size="180x320", audio=None)
        dt = check_delivery(tiny, ["tiktok"])[0]
        assert dt["status"] == "fail" and any("no audio" in m["message"] for m in dt["findings"]), dt
        checks += 3

        caps = t / "caps.json"
        caps.write_text(json.dumps([
            {"id": "s1", "text": "Each report costs up to 20k.", "say": "x", "start": 0.0, "duration": 4.0},
            {"id": "s2", "text": "This caption leaves before anyone can read it", "start": 4.0, "end": 4.8},
            {"id": "s3", "text": "Licence fine print", "start": 5.0, "end": 5.2, "pass": True}]))
        rd = check_reading(caps)
        assert rd["status"] == "fail" and [e["id"] for e in rd["events"]] == ["s2"], rd
        caps.write_text(json.dumps({"segments": [{"text": "Olá, tudo bem?", "start": 0.0, "end": 2.6}]}))
        assert check_reading(caps)["status"] == "pass"
        caps.write_text(json.dumps([{"word": "Olá", "start": 0.0, "end": 0.3}]))
        assert check_reading(caps)["status"] == "skip"
        caps.write_text(json.dumps([{"text": "日本語のテキスト", "start": 0, "end": 2.0}]))
        assert check_reading(caps)["status"] == "fail"   # 8 CJK chars need 8/4.5 + 1.5 = 3.3 s
        checks += 4

        font = t / "tiny.ttf"
        font.write_bytes(_tiny_font(set(range(0x20, 0x7F)) | {0xE1, 0xE3}))
        assert check_fonts(str(font), ["Olá, tudo bem?"])["status"] == "pass"
        fc = check_fonts(str(font), ["Olá, ação"])
        assert fc["status"] == "fail" and fc["missing"] == ["U+00E7 ç"], fc
        woff = t / "tiny.woff"
        woff.write_bytes(_woff(font.read_bytes()))
        assert check_fonts(str(woff), ["ação"])["missing"] == ["U+00E7 ç"]
        checks += 3

        # --- fixes after review: each defect it found gets a case
        # a damaged stream is an error, never a pass: zeroed mdat (concealed frames), a cut file
        raw = clean.read_bytes()
        m = len(raw)
        corrupt = t / "corrupt.mp4"
        corrupt.write_bytes(raw[:int(m * 0.3)] + bytes(int(m * 0.7) - int(m * 0.3)) + raw[int(m * 0.7):])
        for name, fn in (("flash", check_flash), ("frames", check_frames)):
            g = guarded(name, fn, corrupt)
            assert [x["status"] for x in g] == ["error"], g
        fast = t / "fast.mp4"
        run(["ffmpeg", "-v", "error", "-y", "-i", str(clean), "-c", "copy", "-movflags", "+faststart", str(fast)])
        short = t / "short.mp4"
        short.write_bytes(fast.read_bytes()[:int(fast.stat().st_size * 0.5)])   # moov intact, half the frames gone
        g = guarded("flash", check_flash, short)
        assert g[0]["status"] == "error", g
        checks += 2

        # a file without moov, a font that is not a font: every check still reports, exit 2
        trunc = t / "trunc.mp4"
        trunc.write_bytes(raw[:4096])
        caps.write_text(json.dumps([{"text": "Olá", "start": 0, "end": 3}]))
        ns = argparse.Namespace(platform="tiktok", captions=str(caps), font=str(font), text=None)
        res = run_checks("all", trunc, ns)
        st = {x["check"]: x["status"] for x in res}
        assert st["flash"] == st["blank"] == st["frames"] == st["delivery"] == st["reading"] == "error", st
        assert st["fonts"] == "pass" and verdict(res)[1] == 2, (st, verdict(res))
        bad_font = t / "bad.ttf"
        bad_font.write_bytes(b"not a font at all")
        assert guarded("fonts", check_fonts, str(bad_font), ["abc"])[0]["status"] == "error"
        assert verdict([result("reading", "skip", "x")]) == (False, 2, 0)          # nothing checked is not ok
        assert verdict([result("flash", "pass", "x"), result("fonts", "warn", "x")]) == (True, 0, 2)
        checks += 4

        # silent audio warns
        silent = make("silent", "testsrc2=s={size}:r=30:d={dur}", audio="anullsrc=r=48000:cl=stereo:d={dur}")
        ds = check_delivery(silent, ["tiktok"])[0]
        assert any("silent" in m["message"] for m in ds["findings"]), ds
        checks += 1

        # captions: null start falls back to t0; unreadable times are counted, never a crash
        caps.write_text(json.dumps([
            {"text": "Null start, t0 given", "start": None, "t0": 0.0, "end": 3.0},
            {"text": "Clock time", "start": "0:01", "end": 3.0},
            {"text": "No end at all", "start": 4.0}]))
        rc = check_reading(caps)
        assert rc["status"] == "warn" and len(rc["dropped"]) == 2 and "2 item(s) not timed" in rc["summary"], rc
        caps.write_text(json.dumps([{"text": "Only bad", "start": "x", "end": "y"}]))
        assert guarded("reading", check_reading, caps)[0]["status"] == "error"
        # one piece is id + text: the same text split under one id merges, under two ids it does not
        same = [{"id": "a", "text": "Hello there friend", "start": 0, "end": 1.0},
                {"id": "a", "text": "Hello there friend", "start": 1.0, "end": 2.8}]
        caps.write_text(json.dumps(same))
        assert check_reading(caps)["status"] == "pass"
        same[1]["id"] = "b"
        caps.write_text(json.dumps(same))
        assert check_reading(caps)["status"] == "fail"
        checks += 4

        # a black clip under 1 s is judged whole
        assert check_blank(make("short_blank", "color=c=black:s={size}:r=30:d={dur}", dur=0.8))["status"] == "fail"
        checks += 1

        # the container comes from ffprobe, not the extension
        mkv = t / "mkv.mp4"
        run(["ffmpeg", "-v", "error", "-y", "-i", str(clean), "-c", "copy", "-f", "matroska", str(mkv)])
        dm = check_delivery(mkv, ["tiktok"])[0]
        assert dm["status"] == "fail" and any("container mkv" in m["message"] for m in dm["findings"]), dm
        mov = t / "mov.mp4"
        run(["ffmpeg", "-v", "error", "-y", "-i", str(clean), "-c", "copy", "-f", "mov", str(mov)])
        assert probe(mov)["container"] == "mov" and probe(clean)["container"] == "mp4"
        checks += 2
    print(f"self-test: {checks} checks ok")
    return 0


# ---------------------------------------------------------------- main
def main():
    if "--self-test" in sys.argv:
        return self_test()
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--self-test", action="store_true", help="build tiny clips and check every check")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("video", nargs="?", help="the rendered file")
    common.add_argument("--platform", help="reels, tiktok, shorts, or several joined by commas")
    common.add_argument("--captions", help="voice JSON, [{text,start,end}] or WhisperX JSON")
    common.add_argument("--font", help="font file (ttf/otf/ttc/woff; woff2 via fc-query) or an installed family name")
    common.add_argument("--text", action="append", help="extra on-screen text for the font check (repeatable)")
    common.add_argument("--json", action="store_true", help="machine-readable output")
    sub = p.add_subparsers(dest="cmd", metavar="CHECK")
    for name, hlp in (("all", "every check that its inputs allow"), ("flash", "WCAG 2.3.1 flashes"),
                      ("blank", "flat, empty stretches"), ("frames", "black seams and glitch frames"),
                      ("banding", "CAMBI banding"), ("delivery", "platform limits (--platform)"),
                      ("reading", "reading time of each text (--captions)"),
                      ("fonts", "glyph coverage (--font with --captions or --text)")):
        sub.add_parser(name, parents=[common], help=hlp)
    a = p.parse_args()
    if not a.cmd:
        p.error("name a check, or all")
    for tool in ("ffmpeg", "ffprobe"):
        if not shutil.which(tool):
            print(f"render_qc: {tool} is not on PATH", file=sys.stderr)
            return 2
    video = None
    if a.video:
        video = Path(a.video).resolve()
        if not video.is_file():
            p.error(f"no such file: {a.video}")
    elif a.cmd not in ("reading", "fonts"):
        p.error(f"{a.cmd} needs a VIDEO")
    if a.cmd == "delivery" and not a.platform:
        p.error("delivery needs --platform")
    if a.cmd == "reading" and not a.captions:
        p.error("reading needs --captions")
    if a.cmd == "fonts" and not (a.font and (a.captions or a.text)):
        p.error("fonts needs --font and --captions or --text")
    return print_report(run_checks(a.cmd, video, a), a.json, str(video or a.captions or a.font))


if __name__ == "__main__":
    sys.exit(main())
