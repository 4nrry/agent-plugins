#!/usr/bin/env python3
"""Check a factual video's spec before anything is rendered or recorded.

  check_sources.py spec.yaml      (or .json)

Exits 1 and lists every problem:
- a fact line (narration or on-screen) without enough opened sources, or citing
  a source id the spec does not define;
- a phrase recorded under `left_out` that appears in any spoken or shown text;
- sides of a contested story whose screen time differs by more than the
  tolerance;
- a synthetic real person.
The spec format is in references/spec.md.
"""

import json
import sys
from pathlib import Path


def load(path):
    text = Path(path).read_text()
    if path.endswith(".json"):
        return json.loads(text)
    try:
        import yaml
    except ImportError:
        sys.exit("PyYAML is missing: pip install pyyaml, or write the spec as .json")
    return yaml.safe_load(text)


def check(spec):
    problems = []
    sources = spec.get("sources") or {}
    need = int(spec.get("min_sources", 2))
    lines = [("narration", ln) for ln in spec.get("narration") or []]
    lines += [("screen", ln) for ln in spec.get("screen") or []]
    for where, ln in lines:
        lid = ln.get("id", "?")
        kind = ln.get("kind", "fact")
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
        if kind not in ("fact", "quote", "question", "framing"):
            problems.append("%s %s has unknown kind %r" % (where, lid, kind))
    shown = [ln.get("text") or "" for _, ln in lines] + [ln.get("caption") or "" for _, ln in lines]
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


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    problems = check(load(sys.argv[1]))
    for p in problems:
        print("-", p)
    print("ok" if not problems else "%d problem(s)" % len(problems))
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
