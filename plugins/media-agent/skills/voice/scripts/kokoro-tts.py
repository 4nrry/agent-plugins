#!/usr/bin/env python3
"""Kokoro-82M text to speech on the CPU (Apache-2.0).

  kokoro-tts.py "text" -o out.wav [--voice pm_alex] [--speed 1.0]

Run it with the Python of an environment that has `kokoro` and `soundfile`
(references/tts.md). The voice's first letter is its language: p Brazilian
Portuguese (pf_dora, pm_alex, pm_santa), a American English, b British English.
Writes 24 kHz mono and prints the duration. --self-test needs neither package.
"""
import argparse
import sys

SAMPLE_RATE = 24000  # Kokoro's output rate


def lang_for(voice):
    """Kokoro names voices <lang><gender>_<name>; the pipeline wants that language code."""
    if len(voice) < 3 or voice[2] != "_" or voice[1] not in "fm":
        raise ValueError(f"not a Kokoro voice name: {voice!r} (expected e.g. pm_alex)")
    return voice[0]


def parse(argv):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("text")
    p.add_argument("-o", "--out", default="kokoro.wav")
    p.add_argument("--voice", default="pm_alex")
    p.add_argument("--speed", type=float, default=1.0)
    return p.parse_args(argv)


def main(argv):
    a = parse(argv)
    try:
        lang = lang_for(a.voice)
    except ValueError as e:
        sys.exit(f"kokoro-tts: {e}")
    import numpy as np
    import soundfile as sf
    from kokoro import KPipeline
    pipe = KPipeline(lang_code=lang)
    chunks = [audio for _, _, audio in pipe(a.text, voice=a.voice, speed=a.speed)]
    if not chunks:
        sys.exit("kokoro-tts: the pipeline returned no audio")
    wav = np.concatenate(chunks)
    sf.write(a.out, wav, SAMPLE_RATE)
    print(f"{a.out} ({len(wav) / SAMPLE_RATE:.1f} s)")


def self_test():
    assert lang_for("pm_alex") == "p" and lang_for("af_heart") == "a" and lang_for("bf_emma") == "b"
    for bad in ("alex", "px_alex", "pm-alex", ""):
        try:
            lang_for(bad)
        except ValueError:
            continue
        raise AssertionError(f"{bad!r} must be refused")
    a = parse(["olá", "-o", "x.wav"])
    assert (a.out, a.voice, a.speed) == ("x.wav", "pm_alex", 1.0)
    print("kokoro-tts self-test: ok")


if __name__ == "__main__":
    self_test() if sys.argv[1:] == ["--self-test"] else main(sys.argv[1:])
