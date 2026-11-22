#!/usr/bin/env python3
"""Fixture test for plugins/crew/hooks/inject.sh.

  check_inject_hook.py --self-test

Pipes sample UserPromptSubmit JSON into the hook. A backend named as a whole
word in the user's own text adds the pointer line; the same word inside a block
the host put in the prompt field (<system-reminder>, <task-notification>, ...)
does not, and neither does a prompt made only of such blocks. Needs bash and
jq; without jq it reports a skip, since the hook then does nothing.
"""
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

HOOK = Path(__file__).resolve().parents[4] / "plugins/crew/hooks/inject.sh"


def run(prompt):
    p = subprocess.run(["bash", str(HOOK)], input=json.dumps({"prompt": prompt}), capture_output=True,
                       text=True, timeout=30)
    return p.returncode, p.stdout, p.stderr


def self_test():
    if not shutil.which("jq"):
        print("self-test skipped: jq not installed, and without it the hook does nothing")
        return 0
    fails = []
    reminder = "<system-reminder>\nContents of CLAUDE.md: ask codex or grok for a second opinion.\n</system-reminder>\n"
    notice = '<task-notification id="a1">\n<result>opencode worker finished</result>\n</task-notification>'
    for label, text, want in [
            ("a plain prompt", "rename this variable", None),
            ("a backend named", "peça um review ao codex", "codex"),
            ("two backends", "compare grok e kimi", "grok kimi"),
            ("a reminder naming backends", reminder + "rename this variable", None),
            ("only a task-notification", notice, None),
            ("a notification, a reminder and nothing else", notice + "\n" + reminder, None),
            ("a side-sessions-event", "<side-sessions-event>\nuse agy\n</side-sessions-event>", None),
            ("a reminder and a real request", reminder + "delegate this slice to opencode", "opencode"),
            ("an unclosed tag is still read", "<system-reminder> use hermes", "hermes")]:
        code, out, err = run(text)
        got = None
        if out:
            got = out.split("(matched: ", 1)[1].split(")", 1)[0] if "(matched: " in out else "unexpected output"
        if (code, got, err) != (0, want, ""):
            fails.append(f"{label}: got {(code, got, err)!r}, expected {(0, want, '')!r}")
    t0 = time.monotonic()
    code, out, err = run("<system-reminder> x\n" * 8000 + "use codex")
    if (code, out, err) != (0, "", "") or time.monotonic() - t0 > 5:
        fails.append(f"8,000 unclosed tags: got {(code, out[:40], err)!r} in {time.monotonic() - t0:.1f}s")
    for f in fails:
        print("FAIL:", f)
    print(f"self-test: {'ok' if not fails else str(len(fails)) + ' failed'}")
    return 1 if fails else 0


if __name__ == "__main__":
    if "--self-test" not in sys.argv[1:]:
        sys.exit(__doc__)
    sys.exit(self_test())
