#!/usr/bin/env python3
"""Seed-VC v1 voice conversion with one fixed recipe (code and weights GPL-3.0):
each line keeps its timing and takes the timbre of the reference recording.

  seed-vc.py REF.wav OUTDIR line1.wav [line2.wav ...] [--repo DIR]

Run it with the Python of the environment that matches the clone (Python 3.10,
torch 2.4.0 from the cu121 index, then references/seed-vc-requirements-lock.txt).
--repo, or SEED_VC_REPO, is a clone of github.com/Plachtaa/seed-vc at commit 51383ef.
The models load once for all lines; each line is converted with seed 42 and written
as OUTDIR/<line name>.wav at 22.05 kHz. The recipe and its sources are in
references/voice-conversion.md. --self-test needs none of the packages.
"""
import argparse
import os
import sys

SEED = 42
# The recipe: upstream inference.py defaults except fp16, which is off.
RECIPE = dict(diffusion_steps=30, length_adjust=1.0, inference_cfg_rate=0.7, f0_condition=False,
              auto_f0_adjust=False, semi_tone_shift=0, checkpoint=None, config=None, fp16=False)


def parse(argv, env=os.environ):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("ref", help="reference recording; only its first 25 s are used")
    p.add_argument("outdir")
    p.add_argument("lines", nargs="+", help="audio files to convert")
    p.add_argument("--repo", default=env.get("SEED_VC_REPO"), help="Seed-VC clone (default: $SEED_VC_REPO)")
    a = p.parse_args(argv)
    if not a.repo or not os.path.isfile(os.path.join(a.repo, "inference.py")):
        p.error("--repo (or SEED_VC_REPO) must be a Seed-VC clone with inference.py")
    names = [os.path.basename(x) for x in a.lines]
    if len(set(names)) != len(names):
        p.error("two lines share a file name; their outputs would overwrite each other")
    return a


def main(argv):
    a = parse(argv)
    ref = os.path.abspath(a.ref)
    outdir = os.path.abspath(a.outdir)
    lines = [os.path.abspath(x) for x in a.lines]
    for f in [ref, *lines]:
        if not os.path.isfile(f):
            sys.exit(f"seed-vc: no such file: {f}")
    import random
    import runpy
    import shutil
    import tempfile
    import numpy as np
    import torch
    repo = os.path.abspath(a.repo)
    os.chdir(repo)                       # inference.py resolves its configs relative to the clone
    sys.path.insert(0, repo)
    g = runpy.run_path("inference.py", run_name="seed_vc")   # not __main__: defines functions only
    loaded = {}
    load_models = g["load_models"]

    def load_once(args):
        if "models" not in loaded:
            loaded["models"] = load_models(args)
        return loaded["models"]
    g["main"].__globals__["load_models"] = load_once
    os.makedirs(outdir, exist_ok=True)
    for src in lines:
        random.seed(SEED)
        np.random.seed(SEED)
        torch.manual_seed(SEED)
        with tempfile.TemporaryDirectory() as tmp:
            g["main"](argparse.Namespace(source=src, target=ref, output=tmp, **RECIPE))
            out = [f for f in os.listdir(tmp) if f.endswith(".wav")]
            if len(out) != 1:
                sys.exit(f"seed-vc: expected one wav for {src}, got {out}")
            shutil.move(os.path.join(tmp, out[0]), os.path.join(outdir, os.path.basename(src)))
        print("ok", os.path.basename(src), flush=True)


def self_test():
    import tempfile
    with tempfile.TemporaryDirectory() as repo:
        open(os.path.join(repo, "inference.py"), "w").close()
        a = parse(["r.wav", "out", "a.wav", "b.wav"], env={"SEED_VC_REPO": repo})
        assert a.repo == repo and a.lines == ["a.wav", "b.wav"]
        assert parse(["r.wav", "out", "a.wav", "--repo", repo], env={}).repo == repo
        for argv, env in ((["r.wav", "out", "x/a.wav", "y/a.wav"], {"SEED_VC_REPO": repo}),
                          (["r.wav", "out", "a.wav"], {}),
                          (["r.wav", "out", "a.wav"], {"SEED_VC_REPO": os.path.join(repo, "missing")})):
            try:
                parse(argv, env=env)
            except SystemExit:
                continue
            raise AssertionError(f"must be refused: {argv} {env}")
    assert RECIPE["diffusion_steps"] == 30 and RECIPE["inference_cfg_rate"] == 0.7 and RECIPE["fp16"] is False
    print("seed-vc self-test: ok")


if __name__ == "__main__":
    self_test() if sys.argv[1:] == ["--self-test"] else main(sys.argv[1:])
