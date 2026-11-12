#!/usr/bin/env python3
"""Chatterbox Multilingual text to speech on an 8 GB GPU (Resemble AI, MIT), with or without a cloned voice.

  chatterbox-tts.py "text" -o out.wav [--ref voice.wav] [--seed N]
  chatterbox-tts.py "text" -o out.wav --model pt-br --source SRC [--ref voice.wav] [--seed N]

Run it with the Python of an environment that has chatterbox-tts (references/tts.md).
Without --ref it speaks in the model's built-in voice.

--model v2 (default) is the multilingual model that chatterbox-tts 0.1.7 from PyPI loads.
--model pt-br is the Brazilian Portuguese pack, ResembleAI/Chatterbox-Multilingual-pt-br,
which 0.1.7 cannot load: SRC is the directory that holds the `chatterbox` package of a
newer upstream checkout (`src/` in a clone of github.com/resemble-ai/chatterbox). Its files
and three from the base model come through the Hugging Face cache at pinned revisions
(about 3 GB the first time) and are linked into one temporary folder.
--self-test needs none of the packages.
"""
import argparse
import os
import random
import sys
import tempfile
import time

BASE = ("ResembleAI/chatterbox", "5bb1f6ee58e50c3b8d408bc82a6d3740c2db6e18")
PTBR = ("ResembleAI/Chatterbox-Multilingual-pt-br", "b3952f18bc2eaa72b9bd7c17d2c4653bcad4770d")
# (repository, revision, file in the repository, name from_local() expects)
PTBR_FILES = [
    (*PTBR, "t3_pt_br.safetensors", "t3_pt_br.safetensors"),
    (*PTBR, "s3gen_v3.pt", "s3gen.pt"),
    (*PTBR, "grapheme_mtl_merged_expanded_v1.json", "grapheme_mtl_merged_expanded_v1.json"),
    (*BASE, "ve.pt", "ve.pt"),
    (*BASE, "conds.pt", "conds.pt"),
    (*BASE, "Cangjie5_TC.json", "Cangjie5_TC.json"),
]


def decoder_problems(missing, unexpected):
    """The V3 decoder file ships without the tokenizer's buffers, which are computed at
    init, so it loads non-strictly; any other missing or unexpected key is an error."""
    return [k for k in missing if not k.startswith("tokenizer.")] + list(unexpected)


def parse(argv):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("text")
    p.add_argument("-o", "--out", default="chatterbox-out.wav")
    p.add_argument("--model", choices=["v2", "pt-br"], default="v2")
    p.add_argument("--source", help="directory holding a newer upstream `chatterbox` package (--model pt-br)")
    p.add_argument("--ref", help="reference audio to clone: 5 to 10 s, clean")
    p.add_argument("--language", default="pt", help="language id, e.g. pt, en (default pt)")
    p.add_argument("--exaggeration", type=float, default=0.5)
    p.add_argument("--cfg", type=float, default=0.5)
    p.add_argument("--seed", type=int)
    a = p.parse_args(argv)
    if a.model == "pt-br" and not (a.source and os.path.isdir(os.path.join(a.source, "chatterbox"))):
        p.error("--model pt-br needs --source DIR with a chatterbox/ package inside")
    return a


def ptbr_folder(dest):
    from huggingface_hub import hf_hub_download
    for repo, rev, name, link in PTBR_FILES:
        os.symlink(hf_hub_download(repo_id=repo, filename=name, revision=rev), os.path.join(dest, link))


def main(argv):
    a = parse(argv)
    if a.source:
        sys.path.insert(0, os.path.abspath(a.source))
    import numpy as np
    import perth
    import torch
    import torchaudio as ta
    if getattr(perth, "PerthImplicitWatermarker", None) is None:   # some builds ship none
        perth.PerthImplicitWatermarker = perth.DummyWatermarker
    import chatterbox
    from chatterbox.mtl_tts import ChatterboxMultilingualTTS
    src = os.path.abspath(a.source) if a.source else None
    if src and os.path.commonpath([src, os.path.abspath(chatterbox.__file__)]) != src:
        sys.exit(f"chatterbox-tts: imported {chatterbox.__file__}, not the package under --source")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    t0 = time.time()
    if a.model == "v2":
        model = ChatterboxMultilingualTTS.from_pretrained(device=device)
    else:
        from chatterbox.models.s3gen import S3Gen
        strict_load = S3Gen.load_state_dict

        def lenient(self, state, strict=True, **kw):
            r = strict_load(self, state, strict=False, **kw)
            bad = decoder_problems(r.missing_keys, r.unexpected_keys)
            if bad:
                raise RuntimeError(f"decoder checkpoint does not match: {bad[:6]}")
            return r
        S3Gen.load_state_dict = lenient
        with tempfile.TemporaryDirectory(prefix="chatterbox-pt-br-") as ckpt:
            ptbr_folder(ckpt)
            model = ChatterboxMultilingualTTS.from_local(ckpt, device, t3_model="t3_pt_br.safetensors")
    if a.seed is not None:
        torch.manual_seed(a.seed)
        torch.cuda.manual_seed_all(a.seed)
        random.seed(a.seed)
        np.random.seed(a.seed)
    wav = model.generate(a.text, language_id=a.language, audio_prompt_path=a.ref,
                         exaggeration=a.exaggeration, cfg_weight=a.cfg)
    ta.save(a.out, wav.cpu(), model.sr)
    print(f"{a.out} ({wav.shape[-1] / model.sr:.1f} s at {model.sr} Hz) in {time.time() - t0:.0f} s")


def self_test():
    assert decoder_problems(["tokenizer._mel_filters", "tokenizer.window"], []) == []
    assert decoder_problems(["tokenizer.window", "flow.encoder.w"], ["extra"]) == ["flow.encoder.w", "extra"]
    links = [link for *_, link in PTBR_FILES]
    assert len(set(links)) == len(links) and "s3gen.pt" in links and "t3_pt_br.safetensors" in links
    assert all(len(rev) == 40 for _, rev, _, _ in PTBR_FILES)
    with tempfile.TemporaryDirectory() as src:
        try:
            parse(["oi", "--model", "pt-br", "--source", src])
        except SystemExit:
            pass
        else:
            raise AssertionError("--source without a chatterbox/ package must be refused")
        os.mkdir(os.path.join(src, "chatterbox"))
        assert parse(["oi", "--model", "pt-br", "--source", src]).model == "pt-br"
    print("chatterbox-tts self-test: ok")


if __name__ == "__main__":
    self_test() if sys.argv[1:] == ["--self-test"] else main(sys.argv[1:])
