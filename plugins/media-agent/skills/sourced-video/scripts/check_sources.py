#!/usr/bin/env python3
"""Check a factual video's spec before anything is rendered or recorded.

  check_sources.py spec.yaml      (or .json)
  check_sources.py --self-test

Exit 0 when the spec passes. Exit 2 when the check did not run (wrong usage, a
spec that cannot be read, PyYAML missing). Exit 1 lists every problem:
- a fact line (narration or on-screen) without the opened sources its level
  needs (news 2, science 1, fiction 1), or citing a source id the spec does
  not define;
- an unknown level, a min_sources below its level's floor (news 2, science and
  fiction 1; the floor still applies to every fact line), or a news line
  marked common or story (news has no unsourced or invented lines);
- a common-knowledge line with a digit in it (a number or date needs a source);
- a phrase recorded under `left_out` that appears in any spoken or shown text;
- sides of a contested story whose screen time differs by more than the
  tolerance;
- a synthetic real person.
The spec format is in references/spec.md.
"""

import json
import sys
from pathlib import Path


def stop(msg):
    """The check did not run: exit 2, so it is not read as a list of problems."""
    print("check_sources: " + msg, file=sys.stderr)
    sys.exit(2)


def load(path):
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as e:
        stop(f"cannot read {path}: {e.strerror}")
    except UnicodeDecodeError:
        stop(f"{path} is not UTF-8 text")
    if path.endswith(".json"):
        try:
            return json.loads(text)
        except ValueError as e:
            stop(f"{path} is not valid JSON: {e}")
    try:
        import yaml
    except ImportError:
        stop("PyYAML is missing: pip install pyyaml, or write the spec as .json")
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError as e:
        stop(f"{path} is not valid YAML: {e}")


# Opened sources a fact line needs, by the spec's level (SKILL.md, "Three levels").
# A real fact inside a story is a science fact: one source.
LEVELS = {"news": 2, "science": 1, "fiction": 1}
KINDS = ("fact", "quote", "question", "framing", "common", "story")


def check(spec):
    problems = []
    sources = spec.get("sources") or {}
    level = spec.get("level", "news")
    if level not in LEVELS:
        problems.append("level %r is unknown: use news, science or fiction" % (level,))
        level = "news"
    floor = LEVELS[level]
    need = int(spec.get("min_sources", floor))
    if need < floor:
        problems.append("min_sources %d is below the %d a %s spec needs" % (need, floor, level))
        need = floor
    default_kind = "story" if level == "fiction" else "fact"
    lines = [("narration", ln) for ln in spec.get("narration") or []]
    lines += [("screen", ln) for ln in spec.get("screen") or []]
    for where, ln in lines:
        lid = ln.get("id", "?")
        kind = ln.get("kind", default_kind)
        ids = ln.get("sources") or []
        unknown = [i for i in ids if i not in sources]
        if unknown:
            problems.append("%s %s cites unknown sources: %s" % (where, lid, ", ".join(unknown)))
        opened = [i for i in ids if i in sources and sources[i].get("opened") is True]
        if kind == "fact" and len(opened) < need:
            problems.append("%s %s is a fact with %d opened source(s), needs %d"
                            % (where, lid, len(opened), need))
        if kind == "quote" and not opened:
            problems.append("%s %s is a quote with no opened source" % (where, lid))
        if kind in ("common", "story") and level == "news":
            problems.append("%s %s is %s, which a news spec cannot have: a fact with %d opened sources"
                            % (where, lid, kind, need))
        if kind == "common" and any(ch.isdigit() for ch in str(ln.get("text") or "") + str(ln.get("caption") or "")):
            problems.append("%s %s is common knowledge with a number in it: a number or date is a fact with a source"
                            % (where, lid))
        if kind not in KINDS:
            problems.append("%s %s has unknown kind %r" % (where, lid, kind))
    shown = [str(ln.get("text") or "") for _, ln in lines] + [str(ln.get("caption") or "") for _, ln in lines]
    blob = "\n".join(shown).lower()
    for item in spec.get("left_out") or []:
        for phrase in item.get("forbid") or []:
            if phrase and phrase.lower() in blob:
                problems.append("left_out %s (%s) leaks: %r"
                                % (item.get("id", "?"), item.get("reason", "?"), phrase))
    sides = spec.get("sides") or []
    if len(sides) >= 2:
        secs = [float(s.get("seconds", 0)) for s in sides]
        tol = float(spec.get("balance_tolerance", 0.1))
        if min(secs) <= 0 or (max(secs) - min(secs)) / max(secs) > tol:
            problems.append("sides are uneven: %s"
                            % ", ".join("%s %.1fs" % (s.get("name", "?"), float(s.get("seconds", 0))) for s in sides))
    if spec.get("synthetic_real_person"):
        problems.append("synthetic_real_person is set: no generated face, voice or body of a real person")
    return problems


def self_test():
    """Each level's rule on small specs; exits 1 on the first mismatch."""
    src = {"a": {"opened": True}, "b": {"opened": True}, "c": {"opened": False}}
    cases = [
        ("news, two opened sources", {"sources": src, "narration": [{"id": "N1", "text": "x", "sources": ["a", "b"]}]}, 0),
        ("news, one opened source", {"sources": src, "narration": [{"id": "N1", "text": "x", "sources": ["a", "c"]}]}, 1),
        ("news, min_sources lowered", {"min_sources": 1, "sources": src, "narration": [{"id": "N1", "text": "x", "sources": ["a"]}]}, 2),
        ("science, min_sources lowered", {"level": "science", "min_sources": 0, "narration": [{"id": "N1", "text": "x"}]}, 2),
        ("a number YAML read as int", {"level": "science", "narration": [{"id": "N1", "kind": "common", "text": 2026}]}, 1),
        ("news, common line", {"sources": src, "narration": [{"id": "N1", "kind": "common", "text": "x"}]}, 1),
        ("news, story line", {"sources": src, "narration": [{"id": "N1", "kind": "story", "text": "x"}]}, 1),
        ("science, one opened source", {"level": "science", "sources": src, "narration": [{"id": "N1", "text": "x", "sources": ["a"]}]}, 0),
        ("science, no source", {"level": "science", "sources": src, "narration": [{"id": "N1", "text": "x"}]}, 1),
        ("science, common knowledge", {"level": "science", "narration": [{"id": "N1", "kind": "common", "text": "A Lua puxa o mar."}]}, 0),
        ("science, common with a number", {"level": "science", "narration": [{"id": "N1", "kind": "common", "text": "Oito vezes mais forte: 8x."}]}, 1),
        ("science, story inside", {"level": "science", "narration": [{"id": "N1", "kind": "story", "text": "A vizinha reclamou."}]}, 0),
        ("fiction, lines default to story", {"level": "fiction", "narration": [{"id": "N1", "text": "O fantasma abriu a porta às 3h."}]}, 0),
        ("fiction, a real fact needs one source", {"level": "fiction", "sources": src, "narration": [{"id": "N1", "kind": "fact", "text": "x"}]}, 1),
        ("unknown level", {"level": "rumor", "narration": []}, 1),
        ("synthetic real person, any level", {"level": "fiction", "synthetic_real_person": True}, 1),
    ]
    for name, spec, want in cases:
        got = len(check(spec))
        if got != want:
            print("self-test failed: %s: %d problem(s), expected %d: %s" % (name, got, want, check(spec)))
            sys.exit(1)
    print("self-test: %d cases ok" % len(cases))
    sys.exit(0)


def main():
    if len(sys.argv) == 2 and sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)
    if len(sys.argv) == 2 and sys.argv[1] == "--self-test":
        self_test()
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        sys.exit(2)
    spec = load(sys.argv[1])
    if not isinstance(spec, dict):
        stop(f"{sys.argv[1]} holds no spec: its top level must be a mapping (see references/spec.md)")
    problems = check(spec)
    for p in problems:
        print("-", p)
    print("ok" if not problems else "%d problem(s)" % len(problems))
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
