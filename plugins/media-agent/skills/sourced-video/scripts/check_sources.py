#!/usr/bin/env python3
"""Check a factual video's spec before anything is rendered or recorded.

  check_sources.py spec.yaml      (or .json)

Exit 0 when the spec passes. Exit 2 when the check did not run (wrong usage, a
spec that cannot be read, PyYAML missing). Exit 1 lists every problem:
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
    if len(sys.argv) == 2 and sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)
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
