#!/usr/bin/env python3
# Adapted from vargHQ/skills, edit-footage-with-code/scripts/analyze_take.py, build_cut.py and
# qa_cut.py (commit 55ac28d), with the defaults of its references/numbers.md
#   MIT License, Copyright (c) 2026 vargai Inc.
#   (loudness slices, room/voice threshold, speech regions, pause and retake rules, quietest-slice
#    cuts, cuts kept clear of picture changes, frame- and sample-numbered filter graph, FCPXML,
#    hot joins, join flashes, the render checks and the heard-text match)
# That MIT licence asks that its copyright notice and permission notice travel with
# substantial portions: the full text is in THIRD_PARTY_NOTICES.md beside this script.
"""Cut dead air and retakes out of a recording by its word times, render the
cut with ffmpeg, and check that no word was cut.

  qa_cut.py plan TAKE --words WORDS.json --out DIR [--cut-fillers] [--min-pause 0.32] ...
  qa_cut.py render DIR/edl.json [--out CUT.mp4] [--fcpxml] [--no-qa]
  qa_cut.py qa CUT.mp4 --edl DIR/edl.json [--heard HEARD.json] [--accept-join S] [--json]
  qa_cut.py --self-test

plan     reads the take's own audio for pauses (word times say which words, not
         where to cut), finds retakes in the words, and writes DIR/edl.json (the
         cut: edit only "in" and "out"), DIR/intended.json (the words the cut
         must still say, with their times in the take), DIR/take.json and
         DIR/review.md. It cuts a retake only when the repeat covers most of the
         earlier attempt, and fillers only with --cut-fillers.
render   recomputes frames and positions from in/out, renders the cut in one
         filter graph trimmed by frame and sample number with a 30 ms fade at
         each join, then runs qa on it (loudness reported, not judged: it is a
         rough cut). --fcpxml also writes cut.fcpxml for a hand trim. A
         variable-frame-rate take is refused (exit 2) with the conform command.
qa       judges a rendered cut: its length against the edit list, joins that
         cut through sound, kept words the edit list clips or drops, pauses over
         0.6 s, an opening on silence, loudness, black and flash frames, and,
         with --heard (a fresh transcript of the cut), the words heard against
         the words intended and any phrase said twice. Writes qa.json,
         contact.jpg and joins.jpg into --out (default: the edit list's folder).

WORDS is WhisperX JSON (segments[].words[] or word_segments), ElevenLabs
Scribe JSON (words[] with type "word"), or a list of {word|text, start, end}
in seconds. A word without times takes the gap between its neighbours.

Exit 0 when every check that ran passed or warned, 1 when one failed, 2 when
nothing failed but a check could not run or nothing was checked. Needs ffmpeg
and ffprobe on PATH; nothing else (no model, no network).
"""

import argparse
import array
import json
import math
import operator
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
import xml.etree.ElementTree as ET
from difflib import SequenceMatcher
from fractions import Fraction
from pathlib import Path
from xml.sax.saxutils import quoteattr

# ---------------------------------------------------------------- defaults
# vargHQ edit-footage-with-code references/numbers.md ("Cutting speech", "Sound") and the
# argparse defaults of its scripts. None was tested against viewers by anyone, its authors say.
WIN = 0.01             # loudness slices of 10 ms; a cut goes in the quietest one
MIN_PAUSE = 0.32       # a pause longer than this inside a thought is shortened ...
KEEP_PAUSE = 0.22      # ... to this
KEEP_SENTENCE = 0.36   # hold after a sentence end
LEAD = 0.05            # room before a first word
TAIL = 0.15            # room after the very last word
MIN_REMOVE = 0.2       # removing less than this on a locked shot is a jump cut for nothing
MIN_RUN = 4            # repeated words that count as a retake
RETAKE_COVER = 0.6     # the repeat must cover this share of the attempt, or it is parallel wording
RETAKE_WINDOW = 40     # words searched ahead for a repeat
FADE_MS = 30           # audio fade at each join
MAX_PAUSE = 0.6        # qa: a pause longer than this in the cut fails
SILENCE_DB = -35.0     # qa: silencedetect level for pauses
OPEN_SILENCE = 0.3     # qa: opening on more silence than this fails
LUFS_TOL = 1.0
TRUE_PEAK = -1.5       # dBTP
MIN_MATCH = 0.95       # heard words against intended words
JOIN_FLASH = 30.0      # mean grey difference (0-255, 64x36) beside a join
# Ours: audio at a cut edge counts as silence only under this absolute level. The take-relative
# speech threshold misses a whispered or trailing word ~30 dB under the voice.
ABS_SILENCE_DB = -50.0
QUIET_MARGIN_DB = 6.0  # a quiet word must also sit this far over the room to count as sound
# Loudness target: vargHQ masters at -14 LUFS; this plugin's voice skill normalizes the
# finished video to -16, so -16 is the default here (--lufs -14 for vargHQ's).
LUFS = -16.0
# Fillers: vargHQ's English list, plus Portuguese hesitations (ours). Only "high" ones are
# ever cut, and only with --cut-fillers. Tokens keep their accents: "há" is a word, "hã" is not.
FILLERS = [(r"^(um+|uh+|er+|ah+|hm+|mm+|hã+|ahn+|hum+)$", 1, "high"), (r"^you know$", 2, "medium"),
           (r"^i mean$", 2, "medium"), (r"^sort of$", 2, "low"), (r"^kind of$", 2, "low"),
           (r"^like$", 1, "low"), (r"^basically$", 1, "low"), (r"^né$", 1, "low"), (r"^tipo$", 1, "low")]


class CheckError(Exception):
    """The step could not run on this input; reported as status "error", exit 2."""


def run(cmd, **kw):
    return subprocess.run(cmd, check=True, capture_output=True, **kw)


def _tail(text, n=300):
    if isinstance(text, bytes):
        text = text.decode("utf-8", "replace")
    return " ".join((text or "").strip().split())[-n:]


def result(check, status, summary, **extra):
    return {"check": check, "status": status, "summary": summary, **extra}


def _seconds(x):
    if isinstance(x, bool):
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def _rate(x):
    n, _, m = (x or "0/1").partition("/")
    try:
        return float(n) / float(m or 1) if float(m or 1) else 0.0
    except ValueError:
        return 0.0


def video_fps(r, avg, name="the file"):
    """The nominal rate, else the average; a stream reporting neither has no usable frame rate."""
    fps, av = _rate(r), _rate(avg)
    if fps <= 0:
        fps = av
    if fps <= 0:
        raise CheckError(f"{name} reports no frame rate (r_frame_rate {r}, avg_frame_rate {avg})")
    return fps, av


def probe(path):
    p = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                        "format=duration:stream=codec_type,width,height,r_frame_rate,avg_frame_rate,sample_rate"
                        ":stream_disposition=attached_pic", "-of", "json", str(path)], capture_output=True, text=True)
    if p.returncode:
        raise CheckError(f"ffprobe cannot read {Path(path).name}: {_tail(p.stderr)}")
    d = json.loads(p.stdout)
    # cover art in an audio file is a one-picture "video" stream at 90000 fps: not a picture to cut
    v = next((s for s in d.get("streams", []) if s["codec_type"] == "video"
              and not (s.get("disposition") or {}).get("attached_pic")), None)
    a = next((s for s in d.get("streams", []) if s["codec_type"] == "audio"), None)
    fps, avg = video_fps(v.get("r_frame_rate"), v.get("avg_frame_rate"), Path(path).name) if v else (0.0, 0.0)
    return {"duration": float(d.get("format", {}).get("duration") or 0), "has_video": v is not None,
            "fps": round(fps, 3) if v else 100.0, "avg_fps": round(avg, 3),
            "vfr": bool(v) and avg > 0 and abs(fps - avg) > 0.005,
            "width": v and v.get("width"), "height": v and v.get("height"),
            "has_audio": a is not None, "sample_rate": int(a["sample_rate"]) if a and a.get("sample_rate") else None}


# ---------------------------------------------------------------- words
def norm(t):
    """Lowercase, letters and digits kept with their accents (vargHQ kept only a-z0-9)."""
    return re.sub(r"[^\w']|_", "", unicodedata.normalize("NFC", str(t)).casefold())


def load_words(path):
    """[{text, start, end}] in spoken order from WhisperX, Scribe or a plain list."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict):
        if isinstance(data.get("word_segments"), list):
            items = data["word_segments"]
        elif isinstance(data.get("segments"), list) and any(
                isinstance(s, dict) and s.get("words") for s in data["segments"]):
            items = [w for s in data["segments"] if isinstance(s, dict) for w in (s.get("words") or [])]
        elif isinstance(data.get("words"), list):      # Scribe, and OpenAI verbose_json beside wordless segments
            items = data["words"]
        elif isinstance(data.get("segments"), list):
            raise CheckError(f"{Path(path).name}: segments carry no words[]; align it for word times")
        else:
            raise CheckError(f"{Path(path).name}: no word_segments, segments[].words or words[]")
    elif isinstance(data, list):
        items = data
    else:
        raise CheckError(f"{Path(path).name}: expected a list of words or WhisperX/Scribe JSON")
    words = []
    for it in items:
        if not isinstance(it, dict) or it.get("type") not in (None, "word"):
            continue                      # Scribe "spacing" and "audio_event" entries
        text = str(it["word"] if it.get("word") is not None else it.get("text") or "").strip()
        if text:
            words.append({"text": text, "start": _seconds(it.get("start")), "end": _seconds(it.get("end"))})
    if not words:
        raise CheckError(f"{Path(path).name}: no words found")
    if sum(len(w["text"].split()) > 2 for w in words) > len(words) / 2:
        raise CheckError(f"{Path(path).name}: a sentence-level list; pass word times (WhisperX or Scribe)")
    if not any(w["start"] is not None and w["end"] is not None for w in words):
        raise CheckError(f"{Path(path).name}: no word has readable start and end times")
    # a word without times (WhisperX leaves lone symbols unaligned) takes the gap between its neighbours
    i, n = 0, len(words)
    while i < n:
        if words[i]["start"] is not None and words[i]["end"] is not None:
            i += 1
            continue
        j = i
        while j < n and (words[j]["start"] is None or words[j]["end"] is None):
            j += 1
        lo = words[i - 1]["end"] if i > 0 else (words[j]["start"] if j < n else 0.0)
        hi = words[j]["start"] if j < n else lo
        step = max(0.0, hi - lo) / (j - i)
        for k in range(i, j):
            words[k]["start"], words[k]["end"] = round(lo + step * (k - i), 3), round(lo + step * (k - i + 1), 3)
            words[k]["filled"] = True
        i = j
    for w in words:
        w["end"] = max(w["end"], w["start"])
    return words


# ---------------------------------------------------------------- audio
_sumprod = getattr(math, "sumprod", None)


def levels(path):
    """RMS of each 10 ms slice in dBFS, mono at 16 kHz."""
    p = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-vn", "-ac", "1", "-ar", "16000",
                        "-f", "s16le", "-"], capture_output=True)
    if p.returncode:
        raise CheckError(f"ffmpeg could not decode the audio of {Path(path).name}: {_tail(p.stderr)}")
    raw = p.stdout
    pcm = array.array("h")
    pcm.frombytes(raw[: len(raw) - len(raw) % 2])
    if sys.byteorder == "big":
        pcm.byteswap()
    n, db = int(16000 * WIN), []
    for i in range(0, len(pcm) - n + 1, n):
        s = pcm[i:i + n]
        ss = _sumprod(s, s) if _sumprod else sum(map(operator.mul, s, s))
        rms = math.sqrt(ss / n) / 32768
        db.append(20 * math.log10(rms) if rms > 0 else -120.0)
    return db


def _pct(vals, p):
    s = sorted(vals)
    return s[min(len(s) - 1, int(len(s) * p))] if s else -120.0


def threshold(db):
    """Between this file's room and its voice, measured rather than fixed (vargHQ analyze_take.py)."""
    live = [d for d in db if d > -80]          # digital silence says nothing about the room
    if not live:
        raise CheckError("no audio above -80 dBFS")
    floor, voice = _pct(live, 0.10), _pct(live, 0.90)
    return max(floor + 0.4 * (voice - floor), voice - 30), floor, voice


def speech_regions(db, th, fill=0.12, blip=0.08):
    regs, start = [], None
    for i, d in enumerate(db + [-120.0]):
        if d >= th and start is None:
            start = i
        elif d < th and start is not None:
            regs.append([start * WIN, i * WIN])
            start = None
    merged = []
    for r in regs:
        if merged and r[0] - merged[-1][1] < fill:
            merged[-1][1] = r[1]
        else:
            merged.append(r)
    return [r for r in merged if r[1] - r[0] >= blip]


def overlap(a, b, regs):
    return sum(max(0.0, min(b, y) - max(a, x)) for x, y in regs)


def quietest(db, a, b):
    """The quietest 10 ms slice between two times: the safest place for a cut."""
    i0, i1 = max(0, int(a / WIN)), min(len(db), max(int(a / WIN) + 1, int(b / WIN)))
    return (min(range(i0, i1), key=lambda i: db[i]) + 0.5) * WIN if i1 > i0 else a


def picture_changes(path):
    """Hard changes and black stretches in the source: a cut must not land beside a slate or a fade."""
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-an", "-vf",
                        "scale=320:-2,select='gt(scene,0.25)',metadata=print:file=-", "-f", "null", "-"],
                       capture_output=True, text=True)
    hard = [float(x) for x in re.findall(r"pts_time:([\d.]+)", r.stdout)]
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-an", "-vf",
                        "blackdetect=d=0.05:pix_th=0.1", "-f", "null", "-"], capture_output=True, text=True)
    black = [[float(a), float(b)] for a, b in re.findall(r"black_start:([\d.]+) black_end:([\d.]+)", r.stderr)]
    return hard, black


# ---------------------------------------------------------------- plan
def retimed(words, regs):
    """Flag words the ASR placed in silence or stretched across a pause. Their times are not moved."""
    out = []
    for w in words:
        a, b = w["start"], w["end"]
        cover = overlap(a, b, regs) / max(b - a, 0.01)
        out.append({**w, "voiced": round(cover, 2), "drifted": cover < 0.25 or b - a > 1.2})
    return out


def pauses_between(regs, words, min_len=0.2):
    out = []
    for k in range(len(regs) - 1):
        a, b = regs[k][1], regs[k + 1][0]
        if b - a < min_len:
            continue
        # the last word that began before the pause ended: nearest-time matching mislabels sentence ends
        before = [w for w in words if w["start"] < b - 0.02]
        prev = before[-1] if before else None
        out.append({"start": round(a, 3), "end": round(b, 3), "len": round(b - a, 3),
                    "after_word": prev["text"] if prev else None,
                    "sentence_end": bool(prev and re.search(r"[.?!…]['\"”»)]*$", prev["text"]))})
    return out


def retake_candidates(words, min_run=MIN_RUN, window=RETAKE_WINDOW):
    toks = [norm(w["text"]) for w in words]
    found, i = [], 0
    while i < len(toks):
        best = None
        for j in range(i + 1, min(i + window, len(toks))):
            n = 0
            while j + n < len(toks) and i + n < j and toks[i + n] == toks[j + n] and toks[i + n]:
                n += 1
            if n >= min_run and (best is None or n > best[1]):
                best = (j, n)
        if best:
            j, n = best
            sure = n / (j - i) >= RETAKE_COVER
            found.append({"attempt_from": i, "attempt_to": j - 1, "kept_from": j, "kept_to": j + n - 1,
                          "start": words[i]["start"], "end": words[j]["start"],
                          "text": " ".join(w["text"] for w in words[i:j]),
                          "repeated": " ".join(w["text"] for w in words[j:j + n]), "run": n,
                          "cover": round(n / (j - i), 2), "sure": sure,
                          "default": "cut the earlier attempt: check which take is really better" if sure
                          else "not cut: this looks like parallel wording; listen first"})
            i = j
        else:
            i += 1
    for n in (1, 2, 3):   # a stutter: the same one to three words twice in a row; flagged, never cut
        for k in range(len(toks) - 2 * n + 1):
            if all(toks[k:k + n]) and toks[k:k + n] == toks[k + n:k + 2 * n] and len("".join(toks[k:k + n])) > 1:
                found.append({"attempt_from": k, "attempt_to": k + n - 1, "kept_from": k + n, "kept_to": k + 2 * n - 1,
                              "start": words[k]["start"], "end": words[k + n]["start"],
                              "text": " ".join(w["text"] for w in words[k:k + n]),
                              "repeated": " ".join(w["text"] for w in words[k + n:k + 2 * n]), "run": n,
                              "cover": 1.0, "sure": False,
                              "default": "check this one alone: a stutter can be emphasis, or the ASR's invention"})
    return sorted(found, key=lambda r: r["start"])


def filler_candidates(words):
    toks = [norm(w["text"]) for w in words]
    out = []
    for i in range(len(toks)):
        for rx, n, conf in FILLERS:
            if i + n <= len(toks) and re.match(rx, " ".join(toks[i:i + n])):
                out.append({"from": i, "to": i + n - 1, "start": words[i]["start"], "end": words[i + n - 1]["end"],
                            "text": " ".join(w["text"] for w in words[i:i + n]), "confidence": conf,
                            "context": " ".join(w["text"] for w in words[max(0, i - 4):i + n + 4])})
    return out


def snap(t, fps, up=False):
    f = t * fps
    return round((math.ceil(f - 1e-6) if up else math.floor(f + 1e-6)) / fps, 4)


def build_edl(info, regs, pauses, retakes, fillers, db, o, hard=(), black=()):
    fps = info["fps"]
    if not regs:
        raise CheckError("no speech found in the take's audio")
    span = [max(0.0, regs[0][0] - o.lead), min(info["duration"], regs[-1][1] + o.tail)]
    raw = []

    def starts_near(t):
        """The speech region this word really opens, judged by the pause in front of it."""
        best = None
        for k in range(1, len(regs)):
            if t - 0.4 <= regs[k][0] <= t + 1.0 and regs[k][0] - regs[k - 1][1] >= 0.15:
                gap = regs[k][0] - regs[k - 1][1]
                if best is None or gap > best[0]:
                    best = (gap, regs[k][0])
        return best[1] if best else None

    for r in retakes:
        if r["run"] < o.min_run or not r["sure"]:
            continue
        opened = starts_near(r["start"])
        s0 = opened - o.lead if opened is not None else quietest(db, max(0, r["start"] - 0.25), r["start"] + 0.1)
        opened = starts_near(r["end"])
        e0 = opened - o.lead if opened is not None else quietest(db, max(s0 + 0.1, r["end"] - 0.3), r["end"] + 0.15)
        if e0 > s0:
            raw.append([s0, e0, "retake: " + r["text"][:80]])
    for p in pauses:
        hold = o.keep_sentence if p["sentence_end"] else o.keep_pause
        if p["len"] >= o.min_pause and p["len"] - hold >= MIN_REMOVE:
            raw.append([p["start"] + hold - o.lead, p["end"] - o.lead, "pause %.2f s, hold %.2f s" % (p["len"], hold)])
    if o.cut_fillers:
        for f in fillers:
            if f["confidence"] == "high":
                raw.append([quietest(db, f["start"] - 0.08, f["start"] + 0.05),
                            quietest(db, f["end"] - 0.05, f["end"] + 0.08), "filler: " + f["text"]])
    raw.sort()
    cuts = []
    for s0, e0, why in raw:
        # two cuts with no speech between them are one cut
        if cuts and (s0 <= cuts[-1]["end"] or (s0 - cuts[-1]["end"] < 0.25 and overlap(cuts[-1]["end"], s0, regs) < 0.1)):
            cuts[-1]["end"] = max(cuts[-1]["end"], e0)
            cuts[-1]["why"] += "; " + why
        else:
            cuts.append({"start": s0, "end": e0, "why": why})
    keep, at = [], span[0]
    for c in cuts:
        if c["start"] > at:
            keep.append([at, min(c["start"], span[1])])
        at = max(at, c["end"])
    if at < span[1]:
        keep.append([at, span[1]])
    # keep clear of slates, fades and camera switches: a stray frame there flashes at the join
    room, moved, f1 = 0.5, [], 1 / fps
    for k in keep:
        for h in hard:
            if k[0] <= h <= k[0] + room:
                moved.append(round(k[0], 3))
                k[0] = h + f1
            elif k[1] - room <= h <= k[1]:
                moved.append(round(k[1], 3))
                k[1] = h - f1
        for b0, b1 in black:
            if b0 < k[1] <= b1 + f1 or (k[0] < b0 < k[1] and k[1] - b0 < room):
                moved.append(round(k[1], 3))
                k[1] = b0 - f1
            if b0 <= k[0] < b1 or (k[0] < b1 < k[1] and b1 - k[0] < room):
                moved.append(round(k[0], 3))
                k[0] = b1 + f1
    keep = [k for k in keep if k[1] > k[0] and overlap(k[0], k[1], regs) >= 0.1]
    segs, t = [], 0
    for s, e in keep:
        s, e = snap(s, fps), snap(e, fps, up=True)
        frames = round((e - s) * fps)
        if frames < 2:
            continue
        segs.append({"id": "s%03d" % (len(segs) + 1), "in": s, "out": round(s + frames / fps, 4),
                     "frames": frames, "at": round(t / fps, 4)})
        t += frames
    for c in cuts:
        c["start"], c["end"] = round(c["start"], 3), round(c["end"], 3)
    return {"source": None, "fps": fps, "has_video": info["has_video"], "frames": t, "duration": round(t / fps, 3),
            "source_duration": info["duration"], "segments": segs, "cuts": cuts, "moved_for_picture": moved}


def review_md(info, th, floor, voice, words, pauses, retakes, fillers, edl, unplaced=()):
    gaps = sum(1 for i in range(1, len(words)) if words[i]["start"] - words[i - 1]["end"] >= 0.4)
    drift = [w for w in words if w["drifted"]]
    L = ["# Take review", "", "| | |", "|---|---|",
         "| Source | %.2f s at %s fps%s |" % (info["duration"], info["fps"],
                                          " **variable frame rate: conform it first**" if info["vfr"] else ""),
         "| Voice / room / cut threshold | %.1f / %.1f / %.1f dBFS |" % (voice, floor, th),
         "| Pauses of 0.4 s or more | audio: %d, word gaps: %d |" % (sum(p["len"] >= 0.4 for p in pauses), gaps),
         "| Words the ASR placed in silence | %d |" % len(drift),
         "| Draft | %.2f s, %d segments |" % (edl["duration"], len(edl["segments"])), ""]
    if edl["moved_for_picture"]:
        L += ["Moved %d cut edge(s) off a slate, fade or camera change: check them on joins.jpg." % len(edl["moved_for_picture"]), ""]
    if unplaced:
        L += ["Words with no sound at their times, left out of intended.json and not checked: " + ", ".join(
            "%s (%.2f-%.2f, %s)" % (u["text"], u["start"], u["end"], u["why"]) for u in unplaced[:12]), ""]
    if drift:
        L += ["Do not cut from these word times: " + ", ".join(
            "%s (%.2f-%.2f)" % (w["text"], w["start"], w["end"]) for w in drift[:12]), ""]
    L += ["## Retake candidates", ""]
    L += ["- %.2f s: \"%s\" then \"%s\". %s" % (r["start"], r["text"][:90], r["repeated"][:60], r["default"])
          for r in retakes] or ["None found. Read the transcript yourself: an ASR tidies some retakes away."]
    L += ["", "## Filler candidates (cut only with --cut-fillers, and only the high ones)", ""]
    L += ["- %.2f s [%s] \"%s\" in: %s" % (f["start"], f["confidence"], f["text"], f["context"])
          for f in fillers] or ["None found. Whisper-family models often drop um and uh: listen before trusting this."]
    L += ["", "## Draft cuts", ""] + ["- %.2f to %.2f: %s" % (c["start"], c["end"], c["why"]) for c in edl["cuts"]]
    return "\n".join(L) + "\n"


def word_level(db, a, b):
    """The loudest 10 ms slice inside a word's span, in dBFS (-120 past the end of the audio)."""
    i0, i1 = max(0, int(a / WIN)), min(len(db), int(math.ceil(b / WIN)))
    return max(db[i0:i1]) if i1 > i0 else -120.0


def place_words(words, regs, db, floor, duration):
    """Regions for quiet words the relative threshold missed, and the words with no sound at all.

    A word mostly outside the speech regions is kept as speech when its own span is louder than
    ABS_SILENCE_DB and QUIET_MARGIN_DB over the room: a whispered or trailing ending. One with no
    such sound, or past the end of the media, was misplaced by the ASR: it is listed, and left out
    of intended.json, since nothing at its times can be checked."""
    added, unplaced = [], []
    for k, w in enumerate(words):
        a, b = w["start"], w["end"]
        if overlap(a, b, regs) / max(b - a, 0.01) >= 0.25:
            continue
        lv = word_level(db, a, b)
        if a < duration and lv > max(ABS_SILENCE_DB, floor + QUIET_MARGIN_DB):
            added.append([max(0.0, a), min(duration, b)])
        else:
            unplaced.append({"index": k, "text": w["text"], "start": a, "end": b, "level_db": round(lv, 1),
                             "why": "past the end of the media" if a >= duration else "no sound at its times"})
    if added:
        merged = []
        for r in sorted([list(x) for x in regs] + added):
            if merged and r[0] - merged[-1][1] < 0.12:
                merged[-1][1] = max(merged[-1][1], r[1])
            else:
                merged.append(r)
        regs = merged
    return regs, added, unplaced


def plan(take, words_path, out, o):
    take = Path(take).resolve()
    info = probe(take)
    if not info["has_audio"]:
        raise CheckError(f"{take.name} has no audio; nothing to read")
    words = load_words(words_path)
    db = levels(take)
    th, floor, voice = threshold(db)
    regs = speech_regions(db, th)
    regs, quiet, unplaced = place_words(words, regs, db, floor, len(db) * WIN)
    hard, black = picture_changes(take) if info["has_video"] else ([], [])
    wr = retimed(words, regs)
    pauses = pauses_between(regs, wr)
    retakes = retake_candidates(wr, o.min_run)
    fillers = filler_candidates(wr)
    edl = build_edl(info, regs, pauses, retakes, fillers, db, o, hard, black)
    edl["source"] = str(take)
    gone = set()
    for r in retakes:
        if r["sure"] and r["run"] >= o.min_run:
            gone.update(range(r["attempt_from"], r["attempt_to"] + 1))
    if o.cut_fillers:
        for f in fillers:
            if f["confidence"] == "high":
                gone.update(range(f["from"], f["to"] + 1))
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    # by word order, not by time: ASR times are the thing not to trust
    skip = gone | {u["index"] for u in unplaced}
    intended = [{"text": w["text"], "start": w["start"], "end": w["end"]} for i, w in enumerate(wr) if i not in skip]
    (out / "edl.json").write_text(json.dumps(edl, indent=1, ensure_ascii=False))
    (out / "intended.json").write_text(json.dumps(intended, indent=0, ensure_ascii=False))
    (out / "take.json").write_text(json.dumps({
        "info": info, "threshold_db": round(th, 1), "room_db": round(floor, 1), "voice_db": round(voice, 1),
        "speech": [[round(x, 3), round(y, 3)] for x, y in regs], "hard_picture_changes": hard, "black": black,
        "pauses": pauses, "retakes": retakes, "fillers": fillers, "quiet_words": quiet, "unplaced_words": unplaced,
        "words": wr}, indent=1, ensure_ascii=False))
    (out / "review.md").write_text(review_md(info, th, floor, voice, wr, pauses, retakes, fillers, edl, unplaced))
    return {"out": str(out), "source_s": info["duration"], "draft_s": edl["duration"], "segments": len(edl["segments"]),
            "cuts": len(edl["cuts"]), "retakes_cut": sum(1 for r in retakes if r["sure"] and r["run"] >= o.min_run),
            "retakes_to_check": sum(1 for r in retakes if not r["sure"]), "fillers": len(fillers),
            "words_removed": len(gone), "quiet_words_kept": len(quiet), "unplaced_words": len(unplaced),
            "vfr": info["vfr"]}


# ---------------------------------------------------------------- render
def ffmpeg_version(banner):
    """(major, minor) from `ffmpeg -version`, or None for a git build (N-12345-g...) or an unknown banner."""
    m = re.search(r"ffmpeg version n?(\d+)\.(\d+)", banner)
    return (int(m.group(1)), int(m.group(2))) if m else None


_FPS_MODE = None


def fps_mode(mode, banner=None):
    """-fps_mode came in ffmpeg 5.1; older builds take the same value through -vsync."""
    global _FPS_MODE
    if banner is not None:
        v = ffmpeg_version(banner)
        return ["-vsync", mode] if v is not None and v < (5, 1) else ["-fps_mode", mode]
    if _FPS_MODE is None:
        p = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True)
        _FPS_MODE = p.stdout.splitlines()[0] if p.stdout else ""
    return fps_mode(mode, _FPS_MODE)


def normalize_edl(edl):
    """Recompute frames and positions from in/out, the only fields edited by hand (vargHQ build_cut.py)."""
    fps, t = edl["fps"], 0
    if not edl.get("segments"):
        raise CheckError("the edit list has no segments")
    for i, s in enumerate(edl["segments"]):
        s["id"] = "s%03d" % (i + 1)
        s["in"] = round(round(float(s["in"]) * fps) / fps, 4)
        s["frames"] = round((float(s["out"]) - s["in"]) * fps)
        if s["frames"] < 1 or s["in"] < 0:
            raise CheckError(f"segment {s['id']} has in {s['in']} and out {s['out']}: nothing to keep")
        s["out"] = round(s["in"] + s["frames"] / fps, 4)
        s["at"] = round(t / fps, 4)
        t += s["frames"]
    edl["frames"], edl["duration"] = t, round(t / fps, 3)
    return edl


def filter_graph(edl, rate, fade_ms, video):
    fps, parts, chain = edl["fps"], [], []
    for i, s in enumerate(edl["segments"]):
        ln = s["frames"] / fps
        f_in, f_out = s.get("fade_in_ms", fade_ms) / 1000, s.get("fade_out_ms", fade_ms) / 1000
        f0 = round(s["in"] * fps)   # by frame number: trims by time gained 2 frames over 14 clips (vargHQ)
        if video:
            parts.append("[0:v]trim=start_frame=%d:end_frame=%d,setpts=PTS-STARTPTS[v%d]" % (f0, f0 + s["frames"], i))
        # by sample number for the same reason: rounded seconds move later joins by a frame
        parts.append("[0:a]atrim=start_sample=%d:end_sample=%d,asetpts=PTS-STARTPTS,afade=t=in:d=%.3f,"
                     "afade=t=out:st=%.4f:d=%.3f[a%d]" % (round(f0 / fps * rate), round((f0 + s["frames"]) / fps * rate),
                                                         f_in, max(0, ln - f_out), f_out, i))
        chain.append(("[v%d][a%d]" % (i, i)) if video else "[a%d]" % i)
    n = len(edl["segments"])
    return ";".join(parts) + ";" + "".join(chain) + "concat=n=%d:v=%d:a=1%s" % (n, 1 if video else 0,
                                                                              "[v][a]" if video else "[a]")


def fcpxml(edl, take, info):
    """The cut for Resolve or Final Cut: each clip points into the whole source, so it keeps its handles."""
    fps = edl["fps"]
    # 29.97-style rates are 1001-based; everything else is a whole number of frames per second
    frame = Fraction(1001, round(fps * 1001)) if abs(fps - round(fps)) > 0.001 else Fraction(1, round(fps))

    def rt(n):
        v = frame * n
        return "%d/%ds" % (v.numerator, v.denominator) if v.denominator != 1 else "%ds" % v.numerator
    total = round(info["duration"] / frame)
    uri = Path(take).resolve().as_uri()
    rows = "\n".join('            <asset-clip name=%s ref="r2" offset="%s" start="%s" duration="%s" format="r1" '
                     'tcFormat="NDF" audioRole="dialogue"/>'
                     % (quoteattr(s["id"]), rt(round(s["at"] / frame)), rt(round(s["in"] / frame)), rt(s["frames"]))
                     for s in edl["segments"])
    return """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE fcpxml>
<fcpxml version="1.9">
  <resources>
    <format id="r1" frameDuration="%s" width="%d" height="%d"/>
    <asset id="r2" name=%s start="0s" duration="%s" hasVideo="1" hasAudio="1" format="r1" audioSources="1" audioChannels="2">
      <media-rep kind="original-media" src=%s/>
    </asset>
  </resources>
  <library>
    <event name="Rough cut">
      <project name="Rough cut">
        <sequence format="r1" duration="%s" tcStart="0s" tcFormat="NDF" audioLayout="stereo" audioRate="48k">
          <spine>
%s
          </spine>
        </sequence>
      </project>
    </event>
  </library>
</fcpxml>
""" % (rt(1), info["width"], info["height"], quoteattr(Path(take).name), rt(total), quoteattr(uri), rt(edl["frames"]), rows)


def render(edl_path, take=None, out=None, fade_ms=FADE_MS, crf=18, preset="veryfast", want_fcpxml=False):
    edl_path = Path(edl_path)
    edl = normalize_edl(json.loads(edl_path.read_text(encoding="utf-8")))
    take = Path(take or edl.get("source") or "")
    if not take.is_file():
        raise CheckError(f"the take {take} is not a file; pass --take")
    info = probe(take)
    if not info["has_audio"]:
        raise CheckError(f"{take.name} has no audio")
    video = info["has_video"]
    if video and info["vfr"]:
        raise CheckError(f"{take.name} has a variable frame rate ({info['fps']} nominal, {info['avg_fps']} average): "
                         "frame-numbered trims would drift from the sound. Conform it first, then plan again: "
                         f"ffmpeg -i {take.name} -vf fps={round(info['fps'])},format=yuv420p -fps_mode cfr "
                         f"-c:a copy {take.stem}.cfr.mp4")
    if video and abs(info["fps"] - edl["fps"]) > 0.01:
        raise CheckError(f"the edit list is at {edl['fps']} fps and {take.name} at {info['fps']}: plan it again")
    last = edl["segments"][-1]["out"]
    if last > info["duration"] + 2 / edl["fps"]:
        raise CheckError(f"the last segment ends at {last} s, after the take's {info['duration']:.3f} s")
    edl_path.write_text(json.dumps(edl, indent=1, ensure_ascii=False))
    out = Path(out) if out else edl_path.parent / ("cut.mp4" if video else "cut.m4a")
    graph = filter_graph(edl, info["sample_rate"], fade_ms, video)
    (edl_path.parent / "filter.txt").write_text(graph)
    cmd = ["ffmpeg", "-v", "error", "-y", "-i", str(take), "-filter_complex", graph]
    if video:
        cmd += ["-map", "[v]", "-c:v", "libx264", "-crf", str(crf), "-preset", preset, *fps_mode("passthrough"),
                "-g", str(max(1, round(edl["fps"]))), "-pix_fmt", "yuv420p"]
    cmd += ["-map", "[a]", "-c:a", "aac", "-b:a", "256k", "-ar", "48000", "-movflags", "+faststart", str(out)]
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode:
        raise CheckError(f"ffmpeg could not render the cut: {_tail(p.stderr)}")
    files = [str(out), str(edl_path.parent / "filter.txt")]
    if want_fcpxml:
        if not video:
            raise CheckError("FCPXML needs a video take")
        fx = edl_path.parent / "cut.fcpxml"
        fx.write_text(fcpxml(edl, take, info))
        files.append(str(fx))
    return out, {"clips": len(edl["segments"]), "duration": edl["duration"], "files": files}


# ---------------------------------------------------------------- qa
def hot_joins(db, ts):
    """Joins where sound is still loud right at the cut: a clipped word that a transcript will not show."""
    live = sorted(d for d in db if d > -80)
    if not live:
        return [], None
    floor, voice = live[int(len(live) * 0.1)], live[int(len(live) * 0.9)]
    th = floor + 0.4 * (voice - floor)
    bad = []
    for t in ts:
        i = int(round(t / WIN))
        before, after = db[max(0, i - 2):i], db[i:i + 2]
        if (before and max(before) > th) or (after and max(after) > th):
            bad.append({"join": round(t, 3), "before_db": round(max(before), 1) if before else None,
                        "after_db": round(max(after), 1) if after else None})
    return bad, round(th, 1)


def gray_frames(video, w=64, h=36):
    raw = run(["ffmpeg", "-v", "error", "-i", str(video), "-vf", f"scale={w}:{h},format=gray",
               "-f", "rawvideo", "-"]).stdout
    size = w * h
    return [raw[i * size:(i + 1) * size] for i in range(len(raw) // size)]


def join_flashes(frames, ts, fps, limit=JOIN_FLASH):
    """A frame beside a join that looks nothing like its own side of the join. Frames are indexed,
    not seeked: a seek can land across the cut and flag every real camera change (vargHQ)."""
    n, bad = len(frames), []
    if not n:
        return bad
    size = len(frames[0])
    for t in ts:
        j = round(t * fps)
        for near, far, side in ((j, j + 4, "after"), (j - 1, j - 5, "before")):
            if 0 <= near < n and 0 <= far < n:
                v = sum(map(abs, map(operator.sub, frames[near], frames[far]))) / size
                if v > limit:
                    bad.append({"join": round(t, 3), "side": side, "difference": round(v, 1)})
    return bad


def check_words(edl, intended, source_db=None):
    """Each kept word against the edit list, in the take's own time: wholly inside a segment, or
    clipped (a segment edge inside it while the take has sound there), or dropped (in no segment).
    Sound means louder than ABS_SILENCE_DB, not the take's speech threshold: a quiet ending is a word."""
    segs = [(s["in"], s["out"]) for s in edl["segments"]]
    edges = sorted({x for s in segs for x in s})
    eps = 0.011
    clipped, dropped, stretched = [], [], []
    for k, w in enumerate(intended):
        a, b = float(w["start"]), float(w["end"])
        if any(i - eps <= a and b <= o + eps for i, o in segs):
            continue
        if not any(min(b, o) - max(a, i) > 0 for i, o in segs):
            dropped.append({"index": k, "word": w["text"], "start": a, "end": b})
            continue
        inside = [e for e in edges if a + eps < e < b - eps] or [min(edges, key=lambda e: abs(e - (a + b) / 2))]
        voiced = None
        if source_db is not None:
            lv = [max(source_db[max(0, int(e / WIN) - 2):int(e / WIN) + 2] or [-120.0]) for e in inside]
            voiced = max(lv) > ABS_SILENCE_DB
        row = {"index": k, "word": w["text"], "start": a, "end": b, "edges": [round(e, 3) for e in inside]}
        if voiced is False:
            stretched.append(row)       # the ASR stretched the word into silence the edit removed
        else:
            row["voiced_at_edge"] = voiced
            clipped.append(row)
    if clipped or dropped:
        bits = []
        if clipped:
            bits.append(f"{len(clipped)} word(s) cut through, first \"{clipped[0]['word']}\" at {clipped[0]['start']:.2f} s")
        if dropped:
            bits.append(f"{len(dropped)} kept word(s) left out, first \"{dropped[0]['word']}\" at {dropped[0]['start']:.2f} s")
        status, summary = "fail", "; ".join(bits)
        if clipped and source_db is None:
            summary += " (take unreadable: the audio at the edge was not checked)"
    elif stretched:
        status = "warn"
        summary = (f"{len(stretched)} word time(s) cross a cut where the take is under {ABS_SILENCE_DB:.0f} dBFS, "
                   f"first \"{stretched[0]['word']}\": "
                   "the ASR stretched them into a pause; listen to that join")
    else:
        status, summary = "pass", f"all {len(intended)} kept words sit inside a segment"
    return result("words", status, summary, clipped=clipped[:30], dropped=dropped[:30], stretched=stretched[:30],
                  source="segment edges against the take's word times and its audio at each edge")


def toks(path_or_list):
    data = json.loads(Path(path_or_list).read_text(encoding="utf-8")) if not isinstance(path_or_list, list) else path_or_list
    if isinstance(data, dict):
        if isinstance(data.get("words"), list) and data["words"]:
            data = data["words"]
        elif isinstance(data.get("word_segments"), list):
            data = data["word_segments"]
        elif isinstance(data.get("segments"), list):
            segs = [s for s in data["segments"] if isinstance(s, dict)]
            data = [w for s in segs for w in (s.get("words") or [{"text": s.get("text", "")}])]
        elif isinstance(data.get("text"), str):          # a plain {"text": ...} transcript
            data = [data["text"]]
        else:
            data = []
    if not isinstance(data, list):
        raise CheckError("expected a list of words, {text}, or WhisperX/Scribe JSON")
    out = []
    for x in data:
        if not isinstance(x, (dict, str)):
            continue                                       # null and other stray items
        if isinstance(x, dict) and x.get("type") not in (None, "word"):
            continue
        text = x if isinstance(x, str) else (x.get("word") if x.get("word") is not None else x.get("text") or "")
        out += [norm(p) for p in re.split(r"[\s-]+", str(text)) if norm(p)]
    return out


def check_heard(heard, intended, min_match):
    """Words heard against words intended; anything unreadable is an "error" result, not an exception,
    so the other checks of the run still report."""
    try:
        h, i = toks(heard), toks(intended)
    except (OSError, ValueError, CheckError, AttributeError, TypeError) as e:
        return result("heard", "error", f"cannot read {Path(heard).name}: {type(e).__name__}: {e}")
    if not h:
        return result("heard", "error", f"{Path(heard).name} has no words: transcribe the cut again")
    sm = SequenceMatcher(None, i, h, autojunk=False)
    match = sm.ratio()
    diff = [{"intended": " ".join(i[x:y]), "heard": " ".join(h[u:v])}
            for tag, x, y, u, v in sm.get_opcodes() if tag != "equal"][:30]
    doubled = sorted({" ".join(h[k:k + n]) for n in (1, 2, 3) for k in range(len(h) - 2 * n + 1)
                      if h[k:k + n] == h[k + n:k + 2 * n]})[:12]
    rep = [" ".join(h[k:k + n]) for n in range(7, 3, -1) for k in range(len(h) - 2 * n + 1)
           if h[k:k + n] == h[k + n:k + 2 * n]]
    bits = []
    if match < min_match:
        bits.append(f"heard text matches the intended cut at {100 * match:.1f}%, needs {100 * min_match:.0f}%: "
                    "a stutter the first transcript hid is a note, a clipped word is a bug")
    if rep:
        bits.append(f"a phrase is said twice in a row: \"{rep[0]}\"")
    summary = "; ".join(bits) or f"{100 * match:.1f}% of the intended words heard, no phrase said twice"
    if doubled and not rep:
        summary += f"; doubled word(s) to settle by ear: {', '.join(doubled[:4])}"
    return result("heard", "fail" if bits else "pass", summary, word_match=round(match, 3), words_heard=len(h),
                  words_intended=len(i), word_diff=diff, doubled_words=doubled, repeats=rep[:5],
                  source="vargHQ qa_cut.py (95% match; a repeat of 4-7 words fails)")


def loudness(video):
    err = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(video), "-vn", "-af",
                          "loudnorm=print_format=json", "-f", "null", "-"], capture_output=True, text=True).stderr
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", err, re.S)
    if not m:
        return None
    j = json.loads(m.group(0))
    return _seconds(j["input_i"]), _seconds(j["input_tp"])


def qa_dir(video, edl_path=None, out=None):
    return Path(out) if out else (Path(edl_path).parent if edl_path else Path(video).parent / "qa")


def qa(video, edl_path=None, intended_path=None, heard=None, accept=(), out=None, o=None):
    o = o or argparse.Namespace(max_pause=MAX_PAUSE, silence_db=SILENCE_DB, lufs=LUFS, lufs_tol=LUFS_TOL,
                                tp=TRUE_PEAK, min_match=MIN_MATCH, no_loudness=False)
    video = Path(video)
    res = []
    info = probe(video)
    if not info["has_audio"]:
        raise CheckError(f"{video.name} has no audio stream")
    dur = info["duration"]
    edl = json.loads(Path(edl_path).read_text(encoding="utf-8")) if edl_path else None
    fps = edl["fps"] if edl else (info["fps"] if info["has_video"] else 100.0)
    joins = [s["at"] for s in edl["segments"][1:]] if edl else []
    if edl:
        # AAC frames can pad a muxed file by a few hundredths, so two video frames are allowed
        off = dur - edl["duration"]
        res.append(result("duration", "fail" if abs(off) > 2 / fps + 0.05 else "pass",
                          f"{dur:.3f} s against the edit list's {edl['duration']:.3f} s ({off:+.3f} s)"))
    db = levels(video)
    if edl:
        hot, th = hot_joins(db, joins)
        kept = [h for h in hot if not any(abs(h["join"] - t) < 0.05 for t in accept)]
        res.append(result("joins", "fail" if kept else "pass",
                          (f"{len(kept)} of {len(joins)} join(s) cut through sound, first at {kept[0]['join']:.2f} s: "
                           "a clipped word a transcript will not show" if kept else
                           f"{len(joins)} join(s), none cut through sound") +
                          (f"; {len(hot) - len(kept)} accepted by hand" if len(hot) > len(kept) else ""),
                          events=kept[:30], accepted=list(accept), threshold_db=th,
                          source="vargHQ qa_cut.py hot_joins: 20 ms each side above room + 0.4 x (voice - room)"))
        ip = Path(intended_path) if intended_path else Path(edl_path).parent / "intended.json"
        if ip.is_file():
            intended = json.loads(ip.read_text(encoding="utf-8"))
            sdb = None
            src = Path(edl.get("source") or "")
            if src.is_file():
                try:
                    sdb = levels(src)
                except CheckError:
                    sdb = None
            res.append(check_words(edl, intended, sdb))
        else:
            res.append(result("words", "skip", f"no {ip.name} beside the edit list (plan writes it)"))
    err = run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(video), "-vn", "-af",
               f"silencedetect=noise={o.silence_db}dB:d=0.2", "-f", "null", "-"], text=True).stderr
    st = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", err)]
    en = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", err)]
    en += [dur] * (len(st) - len(en))           # a silence running to the end has no end line
    gaps = [(round(max(0.0, s), 2), round(e, 2), round(e - max(0.0, s), 2)) for s, e in zip(st, en)]
    long_gaps = [g for g in gaps if g[2] > o.max_pause and g[0] > 0.05 and g[1] < dur - 0.05]
    bits = []
    if long_gaps:
        bits.append(f"{len(long_gaps)} pause(s) over {o.max_pause} s, first at {long_gaps[0][0]:.2f} s")
    if gaps and gaps[0][0] < 0.05 and gaps[0][2] > OPEN_SILENCE:
        bits.append(f"opens on {gaps[0][2]:.2f} s of silence")
    res.append(result("pauses", "fail" if bits else "pass", "; ".join(bits) or
                      f"no pause over {o.max_pause} s ({len(gaps)} pause(s) of 0.2 s or more)",
                      events=[{"start": a, "end": b, "len": c} for a, b, c in long_gaps[:30]],
                      source=f"vargHQ qa_cut.py: silencedetect at {o.silence_db} dB, 0.6 s limit"))
    ld = loudness(video)
    if ld and ld[0] is not None:
        i, tp = ld
        bits = []
        if abs(i - o.lufs) > o.lufs_tol:
            bits.append(f"{i:.1f} LUFS, target {o.lufs} ± {o.lufs_tol}")
        if tp is not None and tp > o.tp:
            bits.append(f"true peak {tp:.1f} dBTP, over {o.tp}")
        status = ("warn" if o.no_loudness else "fail") if bits else "pass"
        res.append(result("loudness", status, ("; ".join(bits) + (" (rough cut: not judged)" if o.no_loudness else ""))
                          if bits else f"{i:.1f} LUFS, true peak {tp:.1f} dBTP", lufs=i, true_peak=tp))
    else:
        res.append(result("loudness", "warn", "loudnorm measured nothing: a silent track?"))
    if info["has_video"]:
        err = run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(video), "-an", "-vf",
                   "blackdetect=d=0.1:pix_th=0.1", "-f", "null", "-"], text=True).stderr
        black = [float(x) for x in re.findall(r"black_start:([\d.]+)", err)]
        sc = run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(video), "-an", "-vf",
                  "scale=320:-2,select='gt(scene,0.2)',metadata=print:file=-", "-f", "null", "-"], text=True).stdout
        hits = [float(x) for x in re.findall(r"pts_time:([\d.]+)", sc)]
        # a flash: the picture changes hard and changes back within a quarter second
        flash = sorted({round(hits[k], 3) for k in range(len(hits) - 1) if hits[k + 1] - hits[k] <= 0.25})
        at_joins = join_flashes(gray_frames(video), joins, fps) if joins else []
        flash = sorted(set(flash) | {x["join"] for x in at_joins})
        bits = []
        if black:
            bits.append("black frames at " + ", ".join(f"{b:.2f}" for b in black[:5]) + " s")
        if flash:
            bits.append("flash frame near " + ", ".join(f"{x:.2f}" for x in flash[:5]) +
                        " s: move that segment's in or out a few frames, then look at joins.jpg")
        res.append(result("picture", "fail" if bits else "pass", "; ".join(bits) or "no black or flash frame",
                          black_at=black[:20], flash_at=flash[:20], join_flash=at_joins[:20],
                          source=f"vargHQ qa_cut.py: blackdetect 0.1 s, scene pairs within 0.25 s, "
                                 f"frame difference over {JOIN_FLASH} beside a join"))
    if heard:
        ip = Path(intended_path) if intended_path else (Path(edl_path).parent / "intended.json" if edl_path else None)
        if ip and ip.is_file():
            res.append(check_heard(heard, str(ip), o.min_match))
        else:
            res.append(result("heard", "error", "--heard needs the intended words (--intended or intended.json)"))
    else:
        res.append(result("heard", "skip", "no --heard transcript of the cut: words heard not compared"))
    # the sheets: what numbers cannot judge
    d = qa_dir(video, edl_path, out)
    d.mkdir(parents=True, exist_ok=True)
    sheets = []
    if info["has_video"]:
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(video), "-vf",
                        "fps=%f,scale=480:-2,tile=5x4" % (20 / max(dur, 1)), "-frames:v", "1",
                        str(d / "contact.jpg")], capture_output=True)
        ts = joins[:24]
        if ts:
            pick = "+".join("between(t,%.3f,%.3f)" % (t - 1.1 / fps, t + 1.1 / fps) for t in ts)
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(video), "-vf",
                            "select='%s',scale=320:-2,tile=6x%d" % (pick, max(1, len(ts) * 3 // 6 + 1)),
                            *fps_mode("vfr"), "-frames:v", "1", str(d / "joins.jpg")], capture_output=True)
        sheets = [str(d / f) for f in ("contact.jpg", "joins.jpg") if (d / f).exists()]
    return res, sheets, d


# ---------------------------------------------------------------- report
ORDER = {"fail": 0, "error": 1, "warn": 2, "skip": 3, "pass": 4}
STILL_ON_YOU = ["listen to every join: can you hear it?", "look at joins.jpg: does each join read as one thought?",
                "settle each doubled word by ear: an ASR invents some and hides others",
                "does the first 3 seconds earn the next 3?"]


def verdict(results):
    checked = sum(r["status"] in ("pass", "warn", "fail") for r in results)
    if any(r["status"] == "fail" for r in results):
        return False, 1, checked
    if any(r["status"] == "error" for r in results) or checked == 0:
        return False, 2, checked
    return True, 0, checked


def report(results, as_json, target, sheets=(), qa_dir=None, extra=None):
    ok, code, checked = verdict(results)
    doc = {"target": target, "ok": ok, "checked": checked, "checks": results, "sheets": list(sheets),
           "still_on_you": STILL_ON_YOU, **(extra or {})}
    if qa_dir:                      # written on every run, errors too: a stale pass must not survive
        try:
            Path(qa_dir).mkdir(parents=True, exist_ok=True)
            Path(qa_dir, "qa.json").write_text(json.dumps(doc, indent=1, ensure_ascii=False))
        except OSError as e:
            print(f"qa_cut: could not write {Path(qa_dir, 'qa.json')}: {e}", file=sys.stderr)
    if as_json:
        print(json.dumps(doc, indent=2, ensure_ascii=False))
        return code
    for k, v in (extra or {}).items():
        print(f"{k}: {v}")
    for r in results:
        print(f"{r['status'].upper():<6}{r['check']:<10}{r['summary']}")
    counts = {s: sum(r["status"] == s for r in results) for s in ORDER}
    print(f"qa_cut: {counts['fail']} fail, {counts['error']} error, {counts['warn']} warn, {counts['skip']} skipped, "
          f"{counts['pass']} pass" + ("; nothing was checked" if not checked else "") +
          (f"; sheets to look at: {', '.join(sheets)}" if sheets else ""))
    return code


def guarded(name, fn, *args, **kw):
    try:
        return fn(*args, **kw), None
    except CheckError as e:
        return None, result(name, "error", str(e))
    except subprocess.CalledProcessError as e:
        tool = Path(str(e.cmd[0])).name if e.cmd else "a tool"
        return None, result(name, "error", f"{tool} exited {e.returncode}: {_tail(e.stderr) or 'no message'}")
    except (OSError, ValueError, KeyError, IndexError, TypeError) as e:
        return None, result(name, "error", f"{type(e).__name__}: {e}")


# ---------------------------------------------------------------- self-test
def self_test():
    """A take of sine bursts for words, with a retake and long pauses: each defect caught, the clean cut passing."""
    for tool in ("ffmpeg", "ffprobe"):
        if not shutil.which(tool):
            print(f"self-test skipped: {tool} not on PATH, and without it the script does nothing")
            return 0
    checks = 0
    with tempfile.TemporaryDirectory() as tmp:
        t = Path(tmp)
        # (word, start, end): an aborted attempt, a full retake, a sentence pause, a mid-thought pause
        spoken, at = [], 0.6
        for group, gap_after in ((["So", "the", "cat", "sat", "on"], 1.0),
                                 (["So", "the", "cat", "sat", "on", "the", "mat."], 1.2),
                                 (["It", "was", "warm"], 0.9), (["and", "quiet."], 0.0)):
            for k, wd in enumerate(group):
                spoken.append((wd, round(at, 2), round(at + 0.25, 2)))
                at += 0.25 + (0.1 if k < len(group) - 1 else gap_after)
        dur = round(at + 0.6, 2)
        expr = "0.4*sin(2*PI*330*t)*(" + "+".join(f"between(t,{a},{b})" for _, a, b in spoken) + ")+0.002*(2*random(0)-1)"
        take = t / "take.mp4"
        run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"testsrc2=s=320x240:r=30:d={dur}",
             "-f", "lavfi", "-i", f"aevalsrc='{expr}':s=48000:d={dur}", "-c:v", "libx264", "-preset", "ultrafast",
             "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest", str(take)])
        words = t / "words.json"
        words.write_text(json.dumps([{"word": w, "start": a, "end": b} for w, a, b in spoken]))
        opts = argparse.Namespace(min_pause=MIN_PAUSE, keep_pause=KEEP_PAUSE, keep_sentence=KEEP_SENTENCE,
                                  lead=LEAD, tail=TAIL, min_run=MIN_RUN, cut_fillers=False)

        # plan: the aborted attempt and both long pauses go, nothing else
        d = t / "edit"
        s = plan(take, words, d, opts)
        edl = json.loads((d / "edl.json").read_text())
        intended = json.loads((d / "intended.json").read_text())
        assert s["retakes_cut"] == 1 and s["words_removed"] == 5, s
        assert [w["text"] for w in intended][:2] == ["So", "the"] and len(intended) == 12, intended
        retake_start = spoken[5][1]
        assert abs(edl["segments"][0]["in"] - (retake_start - LEAD)) < 0.05, edl["segments"][0]
        # expected: retake to last word + tail, minus (1.2 - 0.36) and (0.9 - 0.22) of pause
        want = (spoken[-1][2] + TAIL) - (retake_start - LEAD) - (1.2 - KEEP_SENTENCE) - (0.9 - KEEP_PAUSE)
        assert abs(edl["duration"] - want) < 0.1, (edl["duration"], want)
        assert len(edl["segments"]) == 3, edl["segments"]
        checks += 4

        # render + qa: the clean cut passes every check that ran
        cut, info = render(d / "edl.json", preset="ultrafast", want_fcpxml=True)
        rough = argparse.Namespace(max_pause=MAX_PAUSE, silence_db=SILENCE_DB, lufs=LUFS, lufs_tol=LUFS_TOL,
                                   tp=TRUE_PEAK, min_match=MIN_MATCH, no_loudness=True)
        res, sheets, _ = qa(cut, d / "edl.json", o=rough)
        st = {r["check"]: r["status"] for r in res}
        assert all(st[k] == "pass" for k in ("duration", "joins", "words", "pauses", "picture")), res
        assert st["loudness"] in ("pass", "warn") and verdict(res)[1] == 0, res
        assert any(p.endswith("joins.jpg") for p in sheets), sheets
        checks += 2

        # FCPXML: well formed, clips laid end to end, total equal to the sequence
        root = ET.parse(d / "cut.fcpxml").getroot()
        seq = root.find(".//sequence")
        clips = seq.findall(".//asset-clip")

        def secs(x):
            return Fraction(x[:-1]) if "/" not in x else Fraction(*map(int, x[:-1].split("/")))
        assert len(clips) == 3 and secs(seq.get("duration")) == sum(secs(c.get("duration")) for c in clips)
        assert all(secs(clips[k].get("offset")) + secs(clips[k].get("duration")) == secs(clips[k + 1].get("offset"))
                   for k in range(len(clips) - 1))
        checks += 1

        # heard: the intended words pass; a phrase said twice fails; half the words missing fails
        heard = t / "heard.json"
        heard.write_text(json.dumps({"segments": [{"words": [{"word": w["text"]} for w in intended]}]}))
        assert check_heard(str(heard), str(d / "intended.json"), MIN_MATCH)["status"] == "pass"
        doubled = [w["text"] for w in intended]
        doubled = doubled[:4] + doubled[:4] + doubled[4:]
        heard.write_text(json.dumps([{"text": x} for x in doubled]))
        hd = check_heard(str(heard), str(d / "intended.json"), 0.5)
        assert hd["status"] == "fail" and "twice" in hd["summary"], hd
        heard.write_text(json.dumps([{"text": w["text"]} for w in intended[::2]]))
        assert check_heard(str(heard), str(d / "intended.json"), MIN_MATCH)["status"] == "fail"
        checks += 3

        # defect: a segment's out moved into the middle of its last word ("warm")
        warm = next(w for w in intended if w["text"] == "warm")
        bad = json.loads((d / "edl.json").read_text())
        seg = next(sg for sg in bad["segments"] if sg["in"] <= warm["start"] < sg["out"])
        seg["out"] = round((warm["start"] + warm["end"]) / 2, 3)
        d2 = t / "clipped"
        d2.mkdir()
        (d2 / "edl.json").write_text(json.dumps(bad))
        (d2 / "intended.json").write_text(json.dumps(intended))
        cut2, _ = render(d2 / "edl.json", preset="ultrafast")
        res, _, _ = qa(cut2, d2 / "edl.json", o=rough)
        st = {r["check"]: r for r in res}
        assert st["joins"]["status"] == "fail", st["joins"]
        assert st["words"]["status"] == "fail" and st["words"]["clipped"][0]["word"] == "warm", st["words"]
        assert verdict(res)[1] == 1
        # the same join accepted by hand no longer fails the joins check
        res, _, _ = qa(cut2, d2 / "edl.json", accept=[st["joins"]["events"][0]["join"]], o=rough)
        assert {r["check"]: r["status"] for r in res}["joins"] == "pass"
        checks += 3

        # defect: a kept word left out in silence, which no audio check can hear
        bad = json.loads((d / "edl.json").read_text())
        mat = next(w for w in intended if w["text"] == "mat.")
        seg = next(sg for sg in bad["segments"] if sg["in"] <= mat["start"] < sg["out"])
        seg["out"] = round(mat["start"] - 0.05, 3)
        wd = check_words(normalize_edl(bad), intended)
        assert wd["status"] == "fail" and wd["dropped"][0]["word"] == "mat.", wd
        # an ASR end stretched into the removed pause only warns when the take is silent at the edge
        stretched = [dict(w) for w in intended]
        for w in stretched:
            if w["text"] == "mat.":
                w["end"] = round(w["end"] + 0.6, 3)
        sdb = levels(take)
        ws = check_words(edl, stretched, sdb)
        assert ws["status"] == "warn" and ws["stretched"][0]["word"] == "mat.", ws
        checks += 2

        # defect: the whole take uncut opens on silence and keeps the long pauses
        whole = {"fps": edl["fps"], "source": str(take), "segments": [{"in": 0, "out": dur - 0.1}]}
        d3 = t / "whole"
        d3.mkdir()
        (d3 / "edl.json").write_text(json.dumps(whole))
        cut3, _ = render(d3 / "edl.json", preset="ultrafast")
        res, _, _ = qa(cut3, d3 / "edl.json", o=rough)
        pz = {r["check"]: r for r in res}["pauses"]
        assert pz["status"] == "fail" and "opens on" in pz["summary"] and len(pz["events"]) >= 2, pz
        checks += 1

        # defect: a white slate frame right after a join
        j = edl["segments"][1]["at"]
        slate = t / "slate.mp4"
        run(["ffmpeg", "-v", "error", "-y", "-i", str(cut), "-vf",
             f"drawbox=c=white:t=fill:enable='eq(n,{round(j * edl['fps'])})'", "-c:v", "libx264", "-preset",
             "ultrafast", "-c:a", "copy", str(slate)])
        res, _, _ = qa(slate, d / "edl.json", o=rough)
        pic = {r["check"]: r for r in res}["picture"]
        assert pic["status"] == "fail" and pic["join_flash"], pic
        checks += 1

        # word files: WhisperX with an unaligned symbol, Scribe with spacing, a sentence list refused
        wx = t / "wx.json"
        wx.write_text(json.dumps({"segments": [{"words": [{"word": "Custa", "start": 1.0, "end": 1.3},
                                                          {"word": "%"}, {"word": "mil", "start": 1.6, "end": 1.9}]}]}))
        ww = load_words(wx)
        assert ww[1]["start"] == 1.3 and ww[1]["end"] == 1.6 and ww[1].get("filled"), ww
        sc = t / "scribe.json"
        sc.write_text(json.dumps({"words": [{"text": "Olá", "start": 0.1, "end": 0.4, "type": "word"},
                                            {"text": " ", "start": 0.4, "end": 0.5, "type": "spacing"},
                                            {"text": "(laughs)", "start": 0.5, "end": 0.9, "type": "audio_event"},
                                            {"text": "mundo", "start": 0.9, "end": 1.2, "type": "word"}]}))
        assert [w["text"] for w in load_words(sc)] == ["Olá", "mundo"]
        sl = t / "sentences.json"
        sl.write_text(json.dumps([{"id": "s1", "text": "Each report costs up to 20k.", "start": 0, "duration": 2}]))
        assert guarded("plan", load_words, sl)[1]["status"] == "error"
        # accents are kept: "há" is a word, "hã" a filler
        fl = filler_candidates([{"text": x, "start": 0, "end": 0} for x in ("Há", "três", "hã", "anos")])
        assert [f["text"] for f in fl if f["confidence"] == "high"] == ["hã"], fl
        checks += 4

        # inputs that cannot be checked: exit 2, never a pass
        silent = t / "silent.mp4"
        run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=160x120:r=30:d=1", "-c:v", "libx264",
             "-preset", "ultrafast", str(silent)])
        _, err = guarded("qa", qa, silent, d / "edl.json", o=rough)
        assert err and err["status"] == "error", err
        _, err = guarded("plan", plan, silent, words, t / "x", opts)
        assert err and err["status"] == "error", err
        assert verdict([result("heard", "skip", "x")]) == (False, 2, 0)
        checks += 3

        # --- fixes after review: each defect it found gets a case
        # a quiet trailing word (~30 dB under the voice), in an audio file with cover art
        qspoken = [("one", 0.5, 0.8, 0.4), ("two", 0.9, 1.2, 0.4), ("three.", 2.4, 2.7, 0.008)]
        qdur = 3.2
        qexpr = "+".join(f"{amp}*sin(2*PI*330*t)*between(t,{a},{b})" for _, a, b, amp in qspoken) + "+0.002*(2*random(0)-1)"
        qtake, cover = t / "quiet.m4a", t / "cover.png"
        run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=red:s=64x64", "-frames:v", "1", str(cover)])
        run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"aevalsrc='{qexpr}':s=48000:d={qdur}",
             "-i", str(cover), "-map", "0:a", "-map", "1:v", "-c:a", "aac", "-b:a", "192k", "-c:v", "png",
             "-disposition:v:0", "attached_pic", str(qtake)])
        assert not probe(qtake)["has_video"], probe(qtake)               # cover art is not a picture to cut
        qwords = t / "quiet.json"                                         # plus a word in a pause and one past the end
        qw = [{"word": w, "start": a, "end": b} for w, a, b, _ in qspoken]
        qw[2:2] = [{"word": "ghost", "start": 1.6, "end": 1.8}]
        qw.append({"word": "four", "start": qdur + 0.3, "end": qdur + 0.6})
        qwords.write_text(json.dumps(qw))
        dq = t / "quiet_edit"
        sq = plan(qtake, qwords, dq, opts)
        qint = json.loads((dq / "intended.json").read_text())
        assert [w["text"] for w in qint] == ["one", "two", "three."] and sq["unplaced_words"] == 2, (sq, qint)
        assert "ghost" in (dq / "review.md").read_text() and sq["quiet_words_kept"] == 1, sq
        qedl = json.loads((dq / "edl.json").read_text())
        assert qedl["segments"][-1]["out"] >= 2.7, qedl                   # the plan keeps the quiet word whole
        qcut, _ = render(dq / "edl.json")
        assert qcut.suffix == ".m4a"
        res, _, _ = qa(qcut, dq / "edl.json", o=rough)
        assert {r["check"]: r["status"] for r in res}["words"] == "pass", res
        qedl["segments"][-1]["out"] = 2.55                                 # the reviewer's repro: out mid-word
        qw = check_words(normalize_edl(qedl), qint, levels(qtake))
        assert qw["status"] == "fail" and qw["clipped"][0]["word"] == "three.", qw
        checks += 6

        # an empty, null-holding or unreadable --heard is an error result beside the other checks
        for body in ("[]", "[null]", "{not json"):
            heard.write_text(body)
            res, _, _ = qa(cut, d / "edl.json", heard=str(heard), o=rough)
            st = {r["check"]: r["status"] for r in res}
            assert st["heard"] == "error" and st["joins"] == st["words"] == "pass" and verdict(res)[1] == 2, (body, res)
        heard.write_text(json.dumps([None, {"text": " ".join(w["text"] for w in intended)}]))
        assert check_heard(str(heard), str(d / "intended.json"), MIN_MATCH)["status"] == "pass"
        heard.write_text(json.dumps({"text": " ".join(w["text"] for w in intended)}))
        assert check_heard(str(heard), str(d / "intended.json"), MIN_MATCH)["status"] == "pass"
        checks += 2

        # an error run overwrites a stale qa.json
        stale = t / "stale"
        stale.mkdir()
        (stale / "qa.json").write_text(json.dumps({"ok": True}))
        pr = subprocess.run([sys.executable, str(Path(__file__).resolve()), "qa", str(silent), "--edl",
                             str(d / "edl.json"), "--out", str(stale)], capture_output=True, text=True)
        doc = json.loads((stale / "qa.json").read_text())
        assert pr.returncode == 2 and doc["ok"] is False and doc["checks"][0]["status"] == "error", (pr, doc)
        checks += 1

        # OpenAI verbose_json: words[] at the top, segments without words
        oa = t / "openai.json"
        oa.write_text(json.dumps({"text": "Olá mundo", "segments": [{"text": "Olá mundo", "start": 0, "end": 1}],
                                  "words": [{"word": "Olá", "start": 0.1, "end": 0.4},
                                            {"word": "mundo", "start": 0.5, "end": 0.9}]}))
        assert [w["text"] for w in load_words(oa)] == ["Olá", "mundo"]
        checks += 1

        # a variable-frame-rate take is refused before it drifts; a stream with no rate is an error
        vfr = t / "vfr.mp4"
        run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=160x120:r=30:d=3", "-f", "lavfi",
             "-i", "sine=f=440:d=3", "-vf", "setpts='if(lt(N,30),N,30+(N-30)*2)/30/TB'", "-fps_mode", "passthrough",
             "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", "-shortest", str(vfr)])
        assert probe(vfr)["vfr"], probe(vfr)
        dv = t / "vfr_edit"
        dv.mkdir()
        (dv / "edl.json").write_text(json.dumps({"fps": probe(vfr)["fps"], "source": str(vfr),
                                                 "segments": [{"in": 0, "out": 1}]}))
        _, err = guarded("render", render, dv / "edl.json")
        assert err and "variable frame rate" in err["summary"] and "-fps_mode cfr" in err["summary"], err
        _, err = guarded("probe", video_fps, "0/0", "0/0")
        assert err and err["status"] == "error" and video_fps("0/0", "30/1")[0] == 30.0, err
        checks += 2

        # -fps_mode only from ffmpeg 5.1; older builds get -vsync
        assert fps_mode("vfr", "ffmpeg version 4.4.2-0ubuntu0.22.04.1 Copyright") == ["-vsync", "vfr"]
        assert fps_mode("vfr", "ffmpeg version n9.0.2-49-gc179411bbb-20261111") == ["-fps_mode", "vfr"]
        assert fps_mode("vfr", "ffmpeg version 5.1.2 Copyright") == ["-fps_mode", "vfr"]
        assert fps_mode("vfr", "ffmpeg version N-112345-gabcdef Copyright") == ["-fps_mode", "vfr"]
        checks += 1
    print(f"self-test: {checks} checks ok")
    return 0


# ---------------------------------------------------------------- main
def main():
    if "--self-test" in sys.argv:
        return self_test()
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--self-test", action="store_true", help="build a take of sine bursts and check every step")
    sub = p.add_subparsers(dest="cmd", metavar="STEP")
    a = sub.add_parser("plan", help="edit list from the take's audio and its word times")
    a.add_argument("take")
    a.add_argument("--words", required=True, help="WhisperX, Scribe or [{word|text, start, end}] JSON")
    a.add_argument("--out", default="edit", help="folder for edl.json, intended.json, take.json, review.md")
    a.add_argument("--min-pause", type=float, default=MIN_PAUSE, help="pauses longer than this get shortened")
    a.add_argument("--keep-pause", type=float, default=KEEP_PAUSE, help="hold inside a thought")
    a.add_argument("--keep-sentence", type=float, default=KEEP_SENTENCE, help="hold after a sentence end")
    a.add_argument("--lead", type=float, default=LEAD, help="room before a first word")
    a.add_argument("--tail", type=float, default=TAIL, help="room after the very last word")
    a.add_argument("--min-run", type=int, default=MIN_RUN, help="repeated words that count as a retake")
    a.add_argument("--cut-fillers", action="store_true", help="also cut um, uh, hã (high-confidence fillers)")
    r = sub.add_parser("render", help="render the edit list, then qa it")
    r.add_argument("edl")
    r.add_argument("--take", help="the source, when the edit list's own path to it is wrong")
    r.add_argument("--out", help="the cut (default: cut.mp4 beside the edit list)")
    r.add_argument("--fade-ms", type=float, default=FADE_MS, help="audio fade at each join; 8 when padding is under 50 ms")
    r.add_argument("--crf", type=int, default=18)
    r.add_argument("--fcpxml", action="store_true", help="also write cut.fcpxml for a hand trim in Resolve or Final Cut")
    r.add_argument("--no-qa", action="store_true")
    q = sub.add_parser("qa", help="check a rendered cut")
    q.add_argument("video")
    q.add_argument("--edl", help="the edit list the cut was rendered from")
    q.add_argument("--intended", help="intended.json (default: beside the edit list)")
    q.add_argument("--heard", help="a fresh transcript of the cut, not of the take")
    q.add_argument("--accept-join", type=float, action="append", default=[],
                   help="a join you listened to and accept, in seconds; repeat for each")
    q.add_argument("--out", help="folder for qa.json and the sheets (default: the edit list's folder)")
    q.add_argument("--max-pause", type=float, default=MAX_PAUSE)
    q.add_argument("--silence-db", type=float, default=SILENCE_DB)
    q.add_argument("--lufs", type=float, default=LUFS, help="loudness target (vargHQ: -14)")
    q.add_argument("--lufs-tol", type=float, default=LUFS_TOL)
    q.add_argument("--tp", type=float, default=TRUE_PEAK, help="true peak ceiling, dBTP")
    q.add_argument("--min-match", type=float, default=MIN_MATCH)
    q.add_argument("--no-loudness", action="store_true", help="rough cut: measure loudness, do not fail on it")
    for x in (a, r, q):
        x.add_argument("--json", action="store_true", help="machine-readable output")
    o = p.parse_args()
    if not o.cmd:
        p.error("name a step: plan, render or qa")
    for tool in ("ffmpeg", "ffprobe"):
        if not shutil.which(tool):
            print(f"qa_cut: {tool} is not on PATH", file=sys.stderr)
            return 2
    if o.cmd == "plan":
        s, err = guarded("plan", plan, o.take, o.words, o.out, o)
        if err:
            print(json.dumps(err) if o.json else f"ERROR plan: {err['summary']}", file=sys.stderr)
            return 2
        print(json.dumps(s, indent=1) if o.json else
              "\n".join(f"{k}: {v}" for k, v in s.items()) +
              f"\nread {Path(o.out) / 'review.md'}, show the plan, and render only after a yes")
        return 0
    if o.cmd == "render":
        rendered, err = guarded("render", render, o.edl, o.take, o.out, o.fade_ms, o.crf, want_fcpxml=o.fcpxml)
        if err:
            return report([err], o.json, o.edl, qa_dir=None if o.no_qa else Path(o.edl).parent)
        cut, info = rendered
        if o.no_qa:
            print(json.dumps(info, indent=1) if o.json else f"rendered {cut}: {info['clips']} clips, {info['duration']} s")
            return 0
        qo = argparse.Namespace(max_pause=MAX_PAUSE, silence_db=SILENCE_DB, lufs=LUFS, lufs_tol=LUFS_TOL,
                                tp=TRUE_PEAK, min_match=MIN_MATCH, no_loudness=True)
        out, err = guarded("qa", qa, cut, o.edl, o=qo)
        if err:
            return report([err], o.json, str(cut), qa_dir=Path(o.edl).parent, extra={"rendered": info})
        res, sheets, d = out
        return report(res, o.json, str(cut), sheets, d, extra={"rendered": info})
    if not Path(o.video).is_file():
        p.error(f"no such file: {o.video}")
    out, err = guarded("qa", qa, o.video, o.edl, o.intended, o.heard, o.accept_join, o.out, o)
    if err:
        return report([err], o.json, o.video, qa_dir=qa_dir(o.video, o.edl, o.out))
    res, sheets, d = out
    return report(res, o.json, o.video, sheets, d)


if __name__ == "__main__":
    sys.exit(main())
