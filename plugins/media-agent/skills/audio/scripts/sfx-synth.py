#!/usr/bin/env python3
"""Synthesize simple sound effects with numpy: no license, no network.

  sfx-synth.py list
  sfx-synth.py NAME -o out.wav [--dur 3] [--seed 1] [--peak -3]

Writes 48 kHz mono 16-bit, peak-normalized to --peak dBFS. Same seed, same file.
"""

import argparse
import sys
import wave

import numpy as np

SR = 48000


def band(x, lo=None, hi=None):
    """FFT band-pass with soft edges."""
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    g = np.ones_like(f)
    if lo:
        g *= 1 / (1 + (lo / np.maximum(f, 1)) ** 4)
    if hi:
        g *= 1 / (1 + (f / hi) ** 4)
    return np.fft.irfft(X * g, len(x))


def env(n, attack, decay):
    t = np.arange(n) / SR
    return np.minimum(t / max(attack, 1e-4), 1.0) * np.exp(-np.maximum(t - attack, 0) / decay)


def norm(x):
    return x / (np.max(np.abs(x)) or 1.0)


class Synth:
    def __init__(self, seed):
        self.rng = np.random.default_rng(seed)

    def noise(self, dur):
        return self.rng.standard_normal(int(dur * SR))

    def static(self, dur):
        """Tape or TV static with crackle; for hard cuts."""
        s = band(self.noise(dur), 800, 9000)
        s += (self.rng.random(len(s)) > 0.997) * self.rng.standard_normal(len(s)) * 6
        k = int(0.01 * SR)
        s[:k] *= np.linspace(0, 1, k)
        s[-k:] *= np.linspace(1, 0, k)
        return s

    def tick(self, dur):
        """Clock tick or UI click."""
        s = band(self.noise(0.04), 1560, 4160) * env(int(0.04 * SR), 0.0005, 0.008)
        t = np.arange(len(s)) / SR
        return s + np.sin(2 * np.pi * 2600 * t) * env(len(t), 0.0005, 0.01) * 0.5

    def thud(self, dur):
        """Something set down on a table."""
        t = np.arange(int(0.4 * SR)) / SR
        s = np.sin(2 * np.pi * 70 * t) * env(len(t), 0.002, 0.07)
        return s + band(self.noise(0.4), 100, 1500) * env(len(t), 0.001, 0.03) * 0.6

    def slam(self, dur):
        """Impact for a title: falling sub thump plus a noise burst."""
        t = np.arange(int(0.9 * SR)) / SR
        sub = np.sin(2 * np.pi * (60 - 25 * t) * t) * np.exp(-t / 0.25)
        return sub * 1.3 + norm(band(self.noise(0.9), 200, 5000) * np.exp(-t / 0.05)) * 0.6

    def rain(self, dur):
        base = band(self.noise(dur), 400, 9000) * 0.6 + band(self.noise(dur), 80, 600) * 0.4
        drops = np.zeros(int(dur * SR))
        for _ in range(int(dur * 60)):
            i = self.rng.integers(0, max(1, len(drops) - 2000))
            d = band(self.noise(0.02), 1500, 6000) * env(int(0.02 * SR), 0.0005, 0.004)
            drops[i:i + len(d)] += d[: len(drops) - i] * self.rng.uniform(0.2, 1.0)
        return norm(base) + norm(drops) * 0.5

    def wind(self, dur):
        """Ambient bed: band noise with a slow swell."""
        t = np.arange(int(dur * SR)) / SR
        lfo = 0.55 + 0.45 * np.sin(2 * np.pi * 0.11 * t) * np.sin(2 * np.pi * 0.047 * t + 1.0)
        return band(self.noise(dur), 150, 1400) * lfo

    def hum(self, dur):
        """Fluorescent or sodium lamp buzz (60 Hz mains harmonics, a little flicker)."""
        t = np.arange(int(dur * SR)) / SR
        h = sum(np.sin(2 * np.pi * 60 * k * t) / k for k in (1, 2, 3, 5, 7))
        return band(h, 50, 1200) * (1 - 0.3 * (np.sin(2 * np.pi * 0.7 * t) > 0.97))

    def typing(self, dur):
        """Keyboard: one key every 90-200 ms."""
        out = np.zeros(int(dur * SR))
        pos = 0.05
        while pos < dur - 0.05:
            d = band(self.noise(0.035), 1200, 7000) * env(int(0.035 * SR), 0.0005, 0.006)
            t = np.arange(len(d)) / SR
            d += np.sin(2 * np.pi * self.rng.uniform(180, 260) * t) * env(len(t), 0.001, 0.01) * 0.4
            i = int(pos * SR)
            out[i:i + len(d)] += norm(d)[: len(out) - i] * self.rng.uniform(0.6, 1.0)
            pos += self.rng.uniform(0.09, 0.2)
        return out

    def heartbeat(self, dur):
        t = np.arange(int(0.6 * SR)) / SR

        def lub(f, g):
            return np.sin(2 * np.pi * f * t * (1 - 0.3 * t)) * env(len(t), 0.004, 0.06) * g

        beat = lub(48, 1.0)
        k = int(0.22 * SR)
        beat[k:] += lub(42, 0.7)[: len(beat) - k]
        beat = band(beat, 20, 300)
        out = np.zeros(int(max(dur, 0.6) * SR))
        for i in range(0, len(out) - len(beat) + 1, int(0.9 * SR)):
            out[i:i + len(beat)] += beat
        return out

    def tv_off(self, dur):
        t = np.arange(int(0.5 * SR)) / SR
        out = np.zeros(int(0.6 * SR))
        pop = band(self.noise(0.08), 50, 3000) * env(int(0.08 * SR), 0.0005, 0.02)
        crack = norm(self.static(0.25)) * np.exp(-np.arange(int(0.25 * SR)) / SR / 0.06)
        out[: len(pop)] += norm(pop)
        out[: len(crack)] += crack * 0.5
        out[: len(t)] += np.sin(2 * np.pi * 7867 * t) * np.exp(-t / 0.12) * 0.15
        return out


NAMES = ["static", "tick", "thud", "slam", "rain", "wind", "hum", "typing", "heartbeat", "tv_off"]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("name", choices=NAMES + ["list"])
    p.add_argument("-o", "--out")
    p.add_argument("--dur", type=float, default=3.0, help="seconds, for beds and loops")
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--peak", type=float, default=-3.0, help="peak level in dBFS")
    a = p.parse_args()
    if a.name == "list":
        for n in NAMES:
            print("%-10s %s" % (n, (getattr(Synth, n).__doc__ or "").strip()))
        return
    if not a.out:
        sys.exit("-o OUT.wav is required")
    sig = norm(getattr(Synth(a.seed), a.name)(a.dur)) * 10 ** (a.peak / 20)
    with wave.open(a.out, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((np.clip(sig, -1, 1) * 32767).astype("<i2").tobytes())
    print("%s  %.2f s" % (a.out, len(sig) / SR))


if __name__ == "__main__":
    main()
