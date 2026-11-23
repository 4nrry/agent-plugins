#!/usr/bin/env python3
# Adapted from digitalsamba/claude-code-video-toolkit, tools/pacing.py
#   read from the fork 4nrry/claude-code-video-toolkit at commit
#   5430de721de2d162e0ee5c02e6d824d7e774c359
#   MIT License, Copyright (c) 2024 Digital Samba
#   (pause-marker stripping, the word count, the 110-170 wpm band and the 6-word floor)
# The MIT licence asks that its copyright notice and permission notice travel with
# substantial portions: the full text is in THIRD_PARTY_NOTICES.md beside this script.
# Not ported: clamp_pace (an in-place atempo slow-down). This script only measures;
# a stretched file changes its duration, so the voice JSON and loudness must be redone.
"""Check the delivery pace of a voice-over, line by line, before it is cut.

  pacing.py VOICE.json [--audio-dir DIR] [--lang pt|en] [--silence-db -40] [--json]
  pacing.py --self-test

VOICE.json is the voice skill's JSON: [{id, text, say, duration, start}], one
sentence per item. The spoken text is `say` (else `text`). The audio of each
line is DIR/<id>.wav (or .mp3, .flac, .m4a, .ogg, .opus) with --audio-dir,
else the item's "file" key (as written by vo-normalize.sh -j). Without audio
the rate is taken over the JSON duration and the pause checks are skipped.

Per line it reports words per minute, syllables per second over the voiced
span (the file minus leading and trailing silence; inner pauses count, as in
Laver's definition of speech rate), the edge silences and the longest inner
pause. Language decides what is judged:

  pt (default)  syllables per second, from a vowel-group syllable counter for
                Portuguese. Words per minute are shown, not judged: Portuguese
                words carry more syllables than English ones, so an English wpm
                band does not carry over.
  en            words per minute, upstream's band.

Exit 0 when every line passed or only warned. Exit 1 when a line failed
(its JSON duration disagrees with its file, so captions and ducking are
timed from a stale number). Exit 2 when nothing failed but a line could not
be checked (no text, no duration and no audio, a missing or undecodable file,
ffmpeg missing) or nothing was checked. Pace and pauses only ever warn: the
norms below were measured on people, not on a TTS.
"""

import argparse
import json
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
from pathlib import Path

# ---------------------------------------------------------------- thresholds
# English, from upstream tools/pacing.py (WARN_FAST_WPM, WARN_SLOW_WPM,
# MIN_WORDS_FOR_LABEL). Upstream's docs/timing.md gives the tiers behind them:
# slow 120-130, standard 140-160, fast 160-180 wpm. House values, not measured.
EN_FAST_WPM = 170
EN_SLOW_WPM = 110
MIN_WORDS_FOR_LABEL = 6   # below this a rate is mostly noise; also applied to pt

# Brazilian Portuguese, syllables per second.
# Almeida, Oliveira Jr., Almeida & Musiliyu, "Percepção de fala comprimida: um
# estudo experimental", Working Papers em Linguística 24(1), 2023, p. 255-256,
# doi:10.5007/1984-8420.2023.e92124: a fluent native speaker of Brazilian
# Portuguese speaks at 3.2 to 5.5 syllables per second (citing Martins & Andrade
# 2008 and Oliveira Jr. 2000).
PT_SLOW_SPS = 3.2
PT_FAST_SPS = 5.5
# Context for the fast line: Dias, Martins, Teixeira & Gama, "Análise da variação
# prosódica em diferentes estilos de reportagens telejornalísticas", Audiology -
# Communication Research 20(3), 2015, doi:10.1590/2317-6431-2014-1528, Table 2:
# TV reporters' narration over pictures ran at 4.80 (informal), 5.47 (serious)
# and 5.55 (neutral) syllables per second. A newsreader's pace sits at the top
# of the band, so a warning near 5.5 on a news-style read is expected.

# House rules, not measured: what a line's audio may carry before it is flagged.
EDGE_SILENCE_S = 0.5      # lead or trail: captions placed at `start` show this early or late
INNER_PAUSE_S = 1.0       # longer than a breath: a dropped word, a stall, two lines merged
MIN_SILENCE_S = 0.15      # shortest gap silencedetect reports
SILENCE_DB = -40          # silence floor, dBFS
UNEVEN = 0.25             # a line this far from the voice-over's median rate stands out
MIN_LINES_FOR_UNEVEN = 3
DURATION_TOL_S = 0.05     # JSON duration vs the file (vo-normalize rounds to 0.01 s)

AUDIO_EXT = (".wav", ".mp3", ".flac", ".m4a", ".ogg", ".opus")

# ---------------------------------------------------------------- text (upstream)
_MARKUP = re.compile(
    r"\[pause[^\]]*\]"          # [pause 1.0s] script markers
    r"|<break[^>]*/?>"          # SSML <break time="1s"/>
    r"|^\[(tone|instruct):[^\]]*\]\s*",  # per-scene header line
    re.IGNORECASE | re.MULTILINE,
)


def spoken_text(text):
    """Script text with pause markers, SSML breaks and tone headers removed."""
    return _MARKUP.sub(" ", text)


def count_words(text):
    """Spoken-word count: ignores pause markers, SSML breaks, tone headers."""
    return len(spoken_text(text).split())


# ---------------------------------------------------------------- pt syllables
STRONG = set("aeoáéóâêôãõà")
WEAK = set("iuy")
ACCENTED_WEAK = set("íú")
VOWELS = STRONG | WEAK | ACCENTED_WEAK


def _hiatus(v1, v2):
    """True when two adjacent vowels belong to different syllables."""
    if v1 in ACCENTED_WEAK or v2 in ACCENTED_WEAK:
        return True                       # sa-ú-de, pa-ís, ru-í-do
    if v1 in STRONG and v2 in STRONG:
        return not (v1 in "ãõ" and v2 in "eo")   # le-ão, po-e-ta; but pão, mães, põe
    if v1 in WEAK and v2 in STRONG:
        return True                       # di-a, ri-o, pi-a-da
    return False                          # pai, céu, muito, viu: one syllable


def syllables_pt(word):
    """Syllables of one Portuguese word by vowel groups. A heuristic, not a
    dictionary: it misses unmarked hiatuses such as ra-i-nha. A final
    unstressed -ia, -io, -ua, -ea, -eo after an accented syllable is one
    syllable (his-tó-ria, ci-ên-cia, ví-deo): the rising diphthong that the
    spelling rule accenting those words assumes, and the way they are spoken."""
    w = word.lower()
    w = re.sub(r"(?<=[qg])[uü](?=[aeioáéíóâêôãõ])", "", w)   # que, guerra, quatro, água: u is silent or a glide
    w = w.replace("ü", "u")
    n, prev = 0, None
    for ch in w:
        if ch in VOWELS:
            if prev is None or _hiatus(prev, ch):
                n += 1
            prev = ch
        else:
            prev = None
    if n > 1 and re.search(r"[áéóâêôíú][^áéóâêôíú]*[^aeiouáéóâêôãõíú][iueo][aeo][sm]?$", w):
        n -= 1
    return max(n, 1)                      # a token with no vowel is an initial read aloud


def count_syllables_pt(text):
    return sum(syllables_pt(w) for w in re.findall(r"[^\W\d_]+", spoken_text(text)))


# ---------------------------------------------------------------- audio
def probe_duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", str(path)], capture_output=True, text=True, timeout=60)
    if out.returncode != 0:
        raise ValueError(f"ffprobe could not read {path}: {out.stderr.strip()[-200:] or 'no message'}")
    return float(out.stdout.strip())


def silences(path, duration, floor_db):
    """[(start, end)] of every silence of MIN_SILENCE_S or more."""
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-v", "info", "-i", str(path), "-af",
                        f"silencedetect=noise={floor_db}dB:d={MIN_SILENCE_S}", "-f", "null", "-"],
                       capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        raise ValueError(f"ffmpeg could not decode {path}: {r.stderr.strip()[-200:] or 'no message'}")
    spans, start = [], None
    for line in r.stderr.splitlines():
        m = re.search(r"silence_start: (-?[\d.]+)", line)
        if m:
            start = max(0.0, float(m.group(1)))
        m = re.search(r"silence_end: (-?[\d.]+)", line)
        if m and start is not None:
            spans.append((start, float(m.group(1))))
            start = None
    if start is not None:                 # silent to the end; older ffmpeg prints no end
        spans.append((start, duration))
    return spans


def audio_shape(path, floor_db):
    """Duration, leading and trailing silence, longest inner pause."""
    dur = probe_duration(path)
    sp = silences(path, dur, floor_db)
    lead = next((e for s, e in sp if s <= 0.01), 0.0)
    if lead >= dur - 0.01:
        raise ValueError(f"{path.name} is silent below {floor_db} dBFS")
    trail = next((dur - s for s, e in sp if e >= dur - 0.01 and s > 0.01), 0.0)
    inner = [e - s for s, e in sp if s > 0.01 and e < dur - 0.01]
    return {"file_duration": round(dur, 3), "lead": round(lead, 3), "trail": round(trail, 3),
            "longest_pause": round(max(inner, default=0.0), 3), "pauses": len(inner)}


# ---------------------------------------------------------------- checks
def find_audio(item, json_dir, audio_dir):
    if audio_dir:
        for ext in AUDIO_EXT:
            p = audio_dir / f"{item.get('id')}{ext}"
            if p.is_file():
                return p
        return audio_dir / f"{item.get('id')}.*"          # reported as missing
    f = item.get("file")
    if not f:
        return None
    for p in (Path(f), json_dir / f):
        if p.is_file():
            return p
    return Path(f)


def label(lang, words, wpm, sps):
    """'fast' | 'slow' | 'ok', or None when the line is too short to judge."""
    if words < MIN_WORDS_FOR_LABEL:
        return None
    if lang == "en":
        return "fast" if wpm > EN_FAST_WPM else "slow" if wpm < EN_SLOW_WPM else "ok"
    return "fast" if sps > PT_FAST_SPS else "slow" if sps < PT_SLOW_SPS else "ok"


def check_line(item, lang, json_dir, audio_dir, floor_db, have_ffmpeg):
    lid = str(item.get("id", "?"))
    out = {"id": lid, "status": "pass", "findings": []}

    def note(level, msg, source):
        out["findings"].append({"level": level, "message": msg, "source": source})
        rank = {"pass": 0, "warn": 1, "error": 2, "fail": 3}
        if rank[level] > rank[out["status"]]:
            out["status"] = level

    text = item.get("say") or item.get("text") or ""
    if not text.strip():
        note("error", "no say or text to measure", "input")
        return out
    words = count_words(text)
    out["words"] = words
    if re.search(r"\d", spoken_text(text)):
        note("warn", "digits in the spoken text: spell them out in `say` (the count here is short)",
             "voice SKILL.md: numbers are spelled out in say")

    span = None
    jdur = item.get("duration")
    path = find_audio(item, json_dir, audio_dir)
    if path is not None:
        if not have_ffmpeg:
            note("error", "ffmpeg or ffprobe is not on PATH; the audio was not read", "input")
        elif not path.is_file():
            note("error", f"no audio file {path}", "input")
        else:
            try:
                shape = audio_shape(path, floor_db)
            except (ValueError, OSError, subprocess.TimeoutExpired) as e:
                note("error", str(e), "ffmpeg")
            else:
                out.update(shape, file=str(path))
                span = shape["file_duration"] - shape["lead"] - shape["trail"]
                if isinstance(jdur, (int, float)) and abs(jdur - shape["file_duration"]) > DURATION_TOL_S:
                    note("fail", f"JSON duration {jdur:.2f} s but the file runs {shape['file_duration']:.2f} s: "
                         "captions and ducking are timed from a stale number",
                         "voice SKILL.md: duration comes from the generated file")
                for side in ("lead", "trail"):
                    if shape[side] > EDGE_SILENCE_S:
                        note("warn", f"{shape[side]:.2f} s of {side}ing silence: trim it, or the caption "
                             f"shows that much {'early' if side == 'lead' else 'late'}",
                             f"house rule, > {EDGE_SILENCE_S} s")
                if shape["longest_pause"] > INNER_PAUSE_S:
                    note("warn", f"a {shape['longest_pause']:.2f} s pause inside the line: listen for a "
                         "dropped word or a stall", f"house rule, > {INNER_PAUSE_S} s")
    if span is None:
        if isinstance(jdur, (int, float)) and jdur > 0:
            span = float(jdur)
            out["timed_from"] = "json duration (edge silence included, reads slightly slow)"
        elif out["status"] != "error":
            note("error", "no duration and no audio", "input")
    if span is None or span <= 0:
        return out

    wpm = round(words / span * 60, 1)
    out.update(span=round(span, 3), wpm=wpm)
    sps = None
    if lang == "pt":
        syl = count_syllables_pt(text)
        sps = round(syl / span, 2)
        out.update(syllables=syl, sps=sps)
    out["pace"] = lab = label(lang, words, wpm, sps)
    if lab in ("fast", "slow"):
        if lang == "en":
            band, src = f"{EN_SLOW_WPM}-{EN_FAST_WPM} wpm", "upstream pacing.py band (house)"
            rate = f"{wpm:.0f} wpm"
        else:
            band, src = f"{PT_SLOW_SPS}-{PT_FAST_SPS} syl/s", "Almeida et al. 2023, fluent pt-BR speech"
            rate = f"{sps:.1f} syl/s"
        note("warn", f"{'rushed' if lab == 'fast' else 'dragging'}: {rate}, outside {band}", src)
    return out


def flag_uneven(lines, lang):
    """Warn on a line far from the voice-over's own median rate (house rule)."""
    key = "sps" if lang == "pt" else "wpm"
    judged = [l for l in lines if l.get("pace") is not None and l.get(key)]
    if len(judged) < MIN_LINES_FOR_UNEVEN:
        return
    med = statistics.median(l[key] for l in judged)
    for l in judged:
        dev = l[key] / med - 1
        if abs(dev) > UNEVEN:
            l["findings"].append({"level": "warn", "source": f"house rule, > {UNEVEN:.0%} from the median",
                                  "message": f"{abs(dev):.0%} {'faster' if dev > 0 else 'slower'} than the "
                                             f"rest of the voice-over (median {med:g} {key})"})
            if l["status"] == "pass":
                l["status"] = "warn"


def load_voice(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("lines") or data.get("sentences") or data.get("items")
    if not isinstance(data, list) or not all(isinstance(i, dict) for i in data):
        raise ValueError("expected a list of {id, say/text, duration} objects")
    return data


def run(voice_json, lang="pt", audio_dir=None, floor_db=SILENCE_DB):
    items = load_voice(voice_json)
    have = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))
    lines = [check_line(i, lang, Path(voice_json).resolve().parent, audio_dir, floor_db, have) for i in items]
    flag_uneven(lines, lang)
    return lines


def verdict(lines):
    checked = sum(l["status"] in ("pass", "warn", "fail") for l in lines)
    if any(l["status"] == "fail" for l in lines):
        return 1
    if any(l["status"] == "error" for l in lines) or checked == 0:
        return 2
    return 0


def report(lines, lang, as_json, target):
    code = verdict(lines)
    if as_json:
        print(json.dumps({"target": target, "lang": lang, "exit": code, "lines": lines},
                         indent=2, ensure_ascii=False))
        return code
    for l in lines:
        rate = (f"{l['sps']:.1f} syl/s  " if "sps" in l else "") + (f"{l['wpm']:.0f} wpm" if "wpm" in l else "")
        edges = (f"  lead {l['lead']:.2f} s  trail {l['trail']:.2f} s  pause {l['longest_pause']:.2f} s"
                 if "lead" in l else "")
        print(f"{l['status'].upper():<6}{l['id']:<10}{rate}{edges}")
        for f in l["findings"]:
            print(f"        {f['level']:<5}{f['message']}  [{f['source']}]")
    counts = {s: sum(l["status"] == s for l in lines) for s in ("fail", "error", "warn", "pass")}
    print(f"pacing: {counts['fail']} fail, {counts['error']} error, {counts['warn']} warn, "
          f"{counts['pass']} pass ({lang})")
    return code


# ---------------------------------------------------------------- self-test
def self_test():
    have = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))
    if not have:   # the repo's CI may lack ffmpeg: say so first, then test what needs no audio
        print("self-test skipped: ffmpeg or ffprobe not on PATH, audio checks not run (text checks follow)")
    checks = 0
    for word, n in (("dia", 2), ("saúde", 3), ("país", 2), ("pai", 1), ("muito", 2), ("quatro", 2),
                    ("que", 1), ("guerra", 2), ("água", 2), ("pão", 1), ("mães", 1), ("leão", 2),
                    ("poesia", 4), ("voo", 2), ("coração", 3), ("Brasil", 2), ("aeroporto", 5),
                    ("ciência", 3), ("história", 3), ("relatório", 4), ("experiência", 5), ("rádio", 2), ("vídeo", 2), ("área", 2), ("ideia", 3), ("praia", 2), ("Uruguai", 3), ("feliz", 2), ("põe", 1)):
        assert syllables_pt(word) == n, (word, syllables_pt(word), n)
        checks += 1
    s = "A casa tem uma porta azul"            # 6 words, 10 syllables
    assert count_words(s) == 6 and count_syllables_pt(s) == 10
    assert count_words("Olá [pause 1.0s] mundo <break time='1s'/>") == 2
    assert label("pt", 6, 0, 5.0) == "ok" and label("pt", 6, 0, 6.0) == "fast" and label("pt", 6, 0, 3.0) == "slow"
    assert label("en", 6, 175, None) == "fast" and label("en", 6, 100, None) == "slow"
    assert label("en", 5, 300, None) is None
    checks += 6
    with tempfile.TemporaryDirectory() as tmp:
        t = Path(tmp)
        no_audio = [{"id": "a", "say": s, "duration": 2.0},                   # 5.0 syl/s
                    {"id": "b", "say": s, "duration": 1.2},                   # 8.3 syl/s
                    {"id": "c", "say": "Custa 20 mil reais por ano", "duration": 2.0},
                    {"id": "d", "text": ""}]
        (t / "v.json").write_text(json.dumps(no_audio), encoding="utf-8")
        got = {l["id"]: l for l in run(t / "v.json")}
        assert got["a"]["status"] == "pass" and got["a"]["sps"] == 5.0, got["a"]
        assert got["b"]["pace"] == "fast" and got["b"]["status"] == "warn"
        assert any("digits" in f["message"] for f in got["c"]["findings"])
        assert got["d"]["status"] == "error" and verdict(list(got.values())) == 2
        en = run_lines([{"id": "e", "say": "This line has exactly seven spoken words", "duration": 2.0}], t, "en")
        assert en[0]["wpm"] == 210.0 and en[0]["pace"] == "fast"
        checks += 5
        if have:
            def tone(name, on, dur):
                """A wav that is a sine wave inside the (start, end) spans in `on` and digital silence elsewhere."""
                expr = "+".join(f"between(t,{a},{b})" for a, b in on)
                subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                                f"aevalsrc='if({expr},0.5*sin(2*PI*220*t),0)':d={dur}:s=48000",
                                str(t / f"{name}.wav")], check=True)
            tone("ok", [(0.3, 2.3)], 2.6)                       # 10 syl over 2.0 s: 5.0, edges 0.3 s
            tone("rush", [(0.3, 1.5)], 1.8)                     # 10 syl over 1.2 s: 8.3
            tone("drag", [(0.8, 1.8), (3.2, 4.2)], 4.3)         # lead 0.8, pause 1.4, span 3.4 s: 2.9
            tone("stale", [(0.3, 2.3)], 2.6)                    # JSON says 3.0 s
            voice = [{"id": "ok", "say": s, "duration": 2.6}, {"id": "rush", "say": s, "duration": 1.8},
                     {"id": "drag", "say": s, "duration": 4.3}, {"id": "stale", "say": s, "duration": 3.0}]
            (t / "a.json").write_text(json.dumps(voice), encoding="utf-8")
            got = {l["id"]: l for l in run(t / "a.json", audio_dir=t)}
            ok = got["ok"]
            assert ok["status"] == "pass" and abs(ok["sps"] - 5.0) < 0.15 and abs(ok["lead"] - 0.3) < 0.05, ok
            assert got["rush"]["pace"] == "fast"
            d = got["drag"]
            assert d["pace"] == "slow" and abs(d["lead"] - 0.8) < 0.05 and abs(d["longest_pause"] - 1.4) < 0.05, d
            msgs = " ".join(f["message"] for f in d["findings"])
            assert "leading silence" in msgs and "pause inside" in msgs, msgs
            assert got["stale"]["status"] == "fail" and verdict(list(got.values())) == 1
            assert any("faster than the rest" in f["message"] for f in got["rush"]["findings"])
            (t / "m.json").write_text(json.dumps([{"id": "missing", "say": s, "duration": 2.0}]), encoding="utf-8")
            assert verdict(run(t / "m.json", audio_dir=t)) == 2
            (t / "x.wav").write_bytes(b"not audio")
            (t / "x.json").write_text(json.dumps([{"id": "x", "say": s, "file": "x.wav"}]), encoding="utf-8")
            bad = run(t / "x.json")
            assert bad[0]["status"] == "error", bad
            cli = subprocess.run([sys.executable, __file__, str(t / "a.json"), "--audio-dir", str(t), "--json"],
                                 capture_output=True, text=True)
            assert cli.returncode == 1 and json.loads(cli.stdout)["exit"] == 1, cli.stderr
            checks += 10
    print(f"self-test: {checks} checks ok")
    return 0


def run_lines(items, tmp, lang):
    p = Path(tmp) / f"lines-{lang}.json"
    p.write_text(json.dumps(items), encoding="utf-8")
    return run(p, lang)


# ---------------------------------------------------------------- main
def main():
    if "--self-test" in sys.argv:
        return self_test()
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("voice_json", help="the voice JSON: [{id, say, text, duration}]")
    p.add_argument("--audio-dir", type=Path, help="folder holding <id>.wav (or mp3, flac, m4a, ogg, opus)")
    p.add_argument("--lang", choices=("pt", "en"), default="pt", help="pt judges syl/s, en judges wpm (default pt)")
    p.add_argument("--silence-db", type=float, default=SILENCE_DB, help=f"silence floor in dBFS (default {SILENCE_DB})")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    p.add_argument("--self-test", action="store_true", help="check the counter and the checks on synthetic audio")
    a = p.parse_args()
    if a.audio_dir and not a.audio_dir.is_dir():
        p.error(f"no such folder: {a.audio_dir}")
    try:
        lines = run(a.voice_json, a.lang, a.audio_dir, a.silence_db)
    except (OSError, ValueError) as e:
        print(f"pacing: cannot read {a.voice_json}: {e}", file=sys.stderr)
        return 2
    return report(lines, a.lang, a.json, a.voice_json)


if __name__ == "__main__":
    sys.exit(main())
