#!/usr/bin/env python3
"""Find frozen frames in a rendered PNG sequence.

Compares consecutive frames (mean absolute difference of the greyscale, 0-255)
and fails when any pair falls under the threshold. Run it on the 3D plates,
before grain, text or noise is added, which would hide a still picture.

  check_motion.py DIR [--glob 'f_*.png'] [--start 0] [--count N] [--threshold 0.05]
"""

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image


def load(path):
    return np.asarray(Image.open(path).convert("L"), np.float32)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("dir")
    p.add_argument("--glob", default="f_*.png")
    p.add_argument("--start", type=int, default=0, help="index of the first frame in the sorted list")
    p.add_argument("--count", type=int, help="frames to check (default: to the end)")
    p.add_argument("--threshold", type=float, default=0.05)
    a = p.parse_args()
    files = sorted(Path(a.dir).glob(a.glob))[a.start:]
    if a.count:
        files = files[:a.count]
    if len(files) < 2:
        sys.exit("need at least 2 frames, found %d in %s" % (len(files), a.dir))
    diffs, still = [], []
    prev = load(files[0])
    for f in files[1:]:
        cur = load(f)
        d = float(np.abs(cur - prev).mean())
        diffs.append(d)
        if d < a.threshold:
            still.append(f.name)
        prev = cur
    d = np.array(diffs)
    print("frames %d  smallest change %.3f  median %.3f  still pairs %d"
          % (len(files), d.min(), float(np.median(d)), len(still)))
    for name in still[:20]:
        print("  still:", name)
    sys.exit(1 if still else 0)


if __name__ == "__main__":
    main()
