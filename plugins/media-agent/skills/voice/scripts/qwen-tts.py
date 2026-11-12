#!/usr/bin/env python3
"""Qwen3-TTS 12 Hz on an 8 GB GPU (Apache-2.0): a voice described in words, or a cloned one.

  qwen-tts.py "text" -o out.wav [--instruct "adult male voice, calm"] [--language Portuguese]
  qwen-tts.py "text" -o out.wav --clone ref.wav [--ref-text "what ref.wav says"]

Run it with the Python of an environment that has `qwen-tts`, `torch` and
`soundfile` (references/tts.md). Without --clone it loads the VoiceDesign model;
with it, the Base model, which clones from the reference (more closely when
--ref-text gives its transcript). The first run of each downloads it.
--self-test needs none of the packages.
"""
import argparse
import sys
import time

DEFAULT_INSTRUCT = "Adult male voice, Brazilian accent, calm institutional tone, clear diction."


def model_id(size, clone):
    return f"Qwen/Qwen3-TTS-12Hz-{size}-{'Base' if clone else 'VoiceDesign'}"


def parse(argv):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("text")
    p.add_argument("-o", "--out", default="qwen-out.wav")
    p.add_argument("--instruct", default=DEFAULT_INSTRUCT, help="the voice, in words (VoiceDesign only)")
    p.add_argument("--clone", help="reference audio to clone (switches to the Base model)")
    p.add_argument("--ref-text", help="transcript of --clone")
    p.add_argument("--language", default="Portuguese")
    p.add_argument("--size", default="1.7B", choices=["0.6B", "1.7B"])
    p.add_argument("--seed", type=int)
    a = p.parse_args(argv)
    if a.ref_text and not a.clone:
        p.error("--ref-text only goes with --clone")
    return a


def main(argv):
    a = parse(argv)
    import soundfile as sf
    import torch
    from qwen_tts import Qwen3TTSModel
    if a.seed is not None:
        torch.manual_seed(a.seed)
    t0 = time.time()
    cuda = torch.cuda.is_available()
    model = Qwen3TTSModel.from_pretrained(model_id(a.size, a.clone), device_map="cuda:0" if cuda else "cpu",
                                          dtype=torch.bfloat16 if cuda else torch.float32)
    if a.clone:
        wavs, sr = model.generate_voice_clone(text=a.text, language=a.language, ref_audio=a.clone,
                                              ref_text=a.ref_text, x_vector_only_mode=a.ref_text is None)
    else:
        wavs, sr = model.generate_voice_design(text=a.text, instruct=a.instruct, language=a.language)
    sf.write(a.out, wavs[0], sr)
    print(f"{a.out} ({len(wavs[0]) / sr:.1f} s at {sr} Hz) in {time.time() - t0:.0f} s")


def self_test():
    assert model_id("1.7B", None) == "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign"
    assert model_id("0.6B", "ref.wav") == "Qwen/Qwen3-TTS-12Hz-0.6B-Base"
    a = parse(["oi", "--clone", "r.wav", "--ref-text", "oi"])
    assert a.clone == "r.wav" and a.language == "Portuguese"
    try:
        parse(["oi", "--ref-text", "oi"])
    except SystemExit:
        pass
    else:
        raise AssertionError("--ref-text without --clone must be refused")
    print("qwen-tts self-test: ok")


if __name__ == "__main__":
    self_test() if sys.argv[1:] == ["--self-test"] else main(sys.argv[1:])
