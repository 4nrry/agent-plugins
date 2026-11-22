#!/usr/bin/env python3
"""Check that sound effects land on the visual movement they belong to.

Pre-render placement (returns suggested SFX start relative to clip start):
  sync_check.py --clip CLIP.mp4 --sfx SFX.wav [--window A:B] [--region W:H:X:Y] [--kind peak|impact|onset]

Post-render verification (exits 1 if |offset| > --tolerance):
  sync_check.py --video OUT.mp4 --sfx SFX.wav --at SEC [--region W:H:X:Y] [--kind peak|impact|onset] [--tolerance 0.1]
  sync_check.py --video OUT.mp4 --cues cues.json [--tolerance 0.1] [--json]
"""

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

try:
    import numpy as np
except ImportError as e:
    if "--self-test" in sys.argv:  # the repo's CI is stdlib-only: skip, loudly, like the hook checks do
        print(f"self-test skipped: {e.name} not installed, and without it the script does nothing")
        sys.exit(0)
    sys.exit(f"sync_check: {e.name} is not installed; it needs numpy")

WIN = 0.05      # RMS audio window (s)
AUDIO_SR = 8000
FPS = 30        # visual sampling rate
SEARCH = 0.5    # search padding around cue window (s)


def peak_from_samples(samples, sample_rate=AUDIO_SR, win_s=WIN):
    """Return (loudest_window_center_s, total_duration_s) from mono float samples."""
    total_s = len(samples) / float(sample_rate) if sample_rate else 0.0
    n = max(1, int(sample_rate * win_s))
    if len(samples) < n:
        return round(total_s / 2.0, 4), total_s
    rms = np.array(
        [np.sqrt(np.mean(samples[i:i + n] ** 2)) for i in range(0, len(samples) - n + 1, n)],
        dtype=np.float32,
    )
    return float(rms.argmax() * win_s + win_s / 2.0), total_s


def sound_peak(sfx):
    """Measure (loudest_50ms_s, length_s) for an audio effect file."""
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(sfx), "-ac", "1", "-ar", str(AUDIO_SR), "-f", "s16le", "-"],
        capture_output=True, check=True,
    ).stdout
    samples = np.frombuffer(raw, np.int16).astype(np.float32) / 32768.0
    return peak_from_samples(samples, AUDIO_SR, WIN)


def motion_event_from_diffs(diffs, t0, fps=FPS, kind="peak"):
    """Find (event_time_s, magnitude) from per-frame mean grey diffs inside [t0, ...].

    kind='peak':   biggest frame-to-frame change (hit, flash, pop).
    kind='impact': sharpest drop after motion (landing, stamp).
    kind='onset':  first frame reaching half of the window's max diff.
    """
    if len(diffs) < 2:
        return float(t0), 0.0
    m = diffs.astype(np.float32, copy=True)
    if len(m) >= 3:
        # Interpolate isolated single duplicate frames (e.g. 24 fps inside 30 fps)
        dup = np.zeros(len(m), dtype=bool)
        dup[1:-1] = (m[1:-1] < 0.02) & (m[:-2] > 0.3) & (m[2:] > 0.3)
        m[dup] = (np.roll(m, 1)[dup] + np.roll(m, -1)[dup]) / 2.0
        m = np.convolve(m, np.ones(3, dtype=np.float32) / 3.0, mode="same")
    if kind == "onset":
        idx = int(np.argmax(m >= 0.5 * m.max()))
        return float(t0 + (idx + 1) / fps), float(m.max())
    if kind == "impact":
        if len(m) <= 3:
            idx = int(m.argmax())
            return float(t0 + (idx + 1) / fps), float(m.max())
        fall = m[:-3] - m[3:]
        idx = int(fall.argmax()) + 3
        return float(t0 + (idx + 1) / fps), float(m.max())
    idx = int(m.argmax())
    return float(t0 + (idx + 1) / fps), float(m[idx])


def full_frame_region(media_path):
    """Return 'W:H:0:0' crop string via ffprobe."""
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "stream=width,height", "-select_streams", "v:0",
         "-of", "csv=p=0", str(media_path)],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    w, h = out.splitlines()[0].split(",")
    return f"{w}:{h}:0:0"


def motion_peak(video, region, t0, t1, kind="peak"):
    """Sample grey frames inside crop `region` over [t0, t1] and detect the motion event."""
    t0 = max(0.0, float(t0))
    dur = max(0.05, float(t1) - t0)
    size = 64
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-ss", f"{t0:.3f}", "-t", f"{dur:.3f}", "-i", str(video),
         "-vf", f"crop={region},fps={FPS},scale={size}:{size},format=gray", "-f", "rawvideo", "-"],
        capture_output=True, check=True,
    ).stdout
    n = len(raw) // (size * size)
    if n < 3:
        return t0, 0.0
    frames = np.frombuffer(raw[:n * size * size], np.uint8).reshape(n, size * size).astype(np.float32)
    diffs = np.abs(np.diff(frames, axis=0)).mean(axis=1)
    return motion_event_from_diffs(diffs, t0, FPS, kind)


def evaluate_offset(seen_s, heard_s, size, tol):
    """Compare visual motion timestamp against audio peak timestamp."""
    off = seen_s - heard_s
    return {
        "sound_peak": round(float(heard_s), 3),
        "movement_peak": round(float(seen_s), 3),
        "offset": round(float(off), 3),
        "shift_sound_by": round(float(off), 3),
        "ok": bool(abs(off) <= tol or size < 0.5),
        "movement": round(float(size), 2),
    }


def check_cue(video, cue, tol):
    """Verify one cue dict {sfx, at, region?, window?, kind?, name?} against `video`."""
    peak, length = sound_peak(Path(cue["sfx"]))
    heard = float(cue["at"]) + peak
    if cue.get("window"):
        w0, w1 = (float(x) for x in str(cue["window"]).split(":"))
    else:
        w0, w1 = float(cue["at"]) - SEARCH, float(cue["at"]) + length + SEARCH
    region = cue.get("region") or full_frame_region(video)
    seen, size = motion_peak(video, region, w0, w1, cue.get("kind", "peak"))
    res = evaluate_offset(seen, heard, size, tol)
    res["name"] = cue.get("name", Path(cue["sfx"]).stem)
    return res


def self_test():
    """Verify audio peak, motion event modes (peak/impact/onset) and offset tolerance on synthetic arrays."""
    sr = 8000
    samples = np.zeros(sr, dtype=np.float32)
    samples[int(0.42 * sr):int(0.47 * sr)] = 0.8
    peak_s, total_s = peak_from_samples(samples, sr, WIN)
    assert abs(total_s - 1.0) < 1e-6, f"unexpected duration {total_s}"
    assert 0.39 <= peak_s <= 0.49, f"expected audio peak ~0.425s, got {peak_s}"

    # 30 diffs (1s at 30 fps) with sustained ramp starting at idx 6 and drop after idx 18
    diffs = np.array(
        [0.05] * 6 + [2.0, 2.2, 2.5, 2.5, 2.5, 2.5, 2.5, 2.5, 2.5, 6.0, 2.5, 2.5, 2.4] + [0.05] * 11,
        dtype=np.float32,
    )
    t_peak, _ = motion_event_from_diffs(diffs, 0.0, FPS, "peak")
    t_onset, _ = motion_event_from_diffs(diffs, 0.0, FPS, "onset")
    t_impact, _ = motion_event_from_diffs(diffs, 0.0, FPS, "impact")
    assert t_onset < t_peak <= t_impact, f"expected onset < peak <= impact, got {t_onset}, {t_peak}, {t_impact}"

    ok_res = evaluate_offset(1.50, 1.44, 5.0, 0.1)
    bad_res = evaluate_offset(1.50, 1.25, 5.0, 0.1)
    assert ok_res["ok"] and not bad_res["ok"], f"unexpected tolerance check: {ok_res}, {bad_res}"
    print("self-test: 4 checks ok")
    return 0


def main():
    if "--self-test" in sys.argv:
        return self_test()
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--video", type=Path, help="rendered video to verify")
    p.add_argument("--clip", type=Path, help="source clip to calculate SFX placement before rendering")
    p.add_argument("--window", help="with --clip: seconds a:b where motion occurs (default: full clip)")
    p.add_argument("--rate", type=float, default=1.0, help="with --clip: playback speed factor")
    p.add_argument("--trim", type=int, default=0, help="with --clip: trimmed frames at start (30 fps)")
    p.add_argument("--sfx", type=Path, help="sound effect file")
    p.add_argument("--at", type=float, help="seconds: where SFX starts in rendered video")
    p.add_argument("--region", help="ffmpeg crop w:h:x:y of the target region (default: full frame)")
    p.add_argument("--name", help="label for single cue")
    p.add_argument("--kind", default="peak", choices=["peak", "impact", "onset"])
    p.add_argument("--cues", type=Path, help="JSON list of {name, sfx, at, region?, window?, kind?}")
    p.add_argument("--tolerance", type=float, default=0.1)
    p.add_argument("--json", action="store_true")
    a = p.parse_args()

    for tool in ("ffmpeg", "ffprobe"):
        if not shutil.which(tool):
            sys.exit(f"sync_check: {tool} is not on PATH")

    if a.clip:
        if not a.sfx:
            p.error("--clip needs --sfx")
        peak, _ = sound_peak(a.sfx)
        w0, w1 = (float(x) for x in a.window.split(":")) if a.window else (0.0, 600.0)
        region = a.region or full_frame_region(a.clip)
        moment, size = motion_peak(a.clip, region, w0, w1, a.kind)
        start = (moment - a.trim / float(FPS)) / a.rate - peak
        print(json.dumps({
            "clip": str(a.clip),
            "movement_at": round(moment, 3),
            "movement": round(size, 2),
            "sound_peak_in_file": round(peak, 3),
            "start_sound_after_clip_s": round(start, 3),
            "start_sound_after_clip_frames_30fps": round(start * FPS),
        }, indent=2))
        return 0

    if not a.video:
        p.error("give --video (check a render) or --clip (place a sound before rendering)")

    if a.cues:
        cues = json.loads(a.cues.read_text(encoding="utf-8"))
        bases = [Path.cwd(), *a.cues.resolve().parents]
        for c in cues:
            found = next((b / c["sfx"] for b in bases if (b / c["sfx"]).exists()), None)
            if found is None:
                p.error(f"cue {c.get('name', '?')}: sound file {c['sfx']} not found")
            c["sfx"] = str(found)
    elif a.sfx and a.at is not None:
        cues = [{"name": a.name or a.sfx.stem, "sfx": str(a.sfx), "at": a.at, "region": a.region, "kind": a.kind}]
    else:
        p.error("give --cues, or --sfx and --at")

    results = [check_cue(a.video, c, a.tolerance) for c in cues]
    if a.json:
        print(json.dumps(results, indent=2))
    else:
        for r in results:
            mark = "ok  " if r["ok"] else "OUT "
            note = "" if r["ok"] else f" -> shift SFX {'later' if r['offset'] > 0 else 'earlier'} by {abs(r['offset']):.2f}s"
            if r["movement"] < 0.5:
                note = " (no clear movement in region)"
            print(f"{mark}{r['name']:<16} sfx {r['sound_peak']:7.2f}s  motion {r['movement_peak']:7.2f}s  "
                  f"offset {r['offset']:+.2f}s{note}")
    return 0 if all(r["ok"] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
