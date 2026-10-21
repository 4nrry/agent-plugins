#!/usr/bin/env python3
"""Check each flag fact the SKILL.md cites against the installed binary.

Why: the `android` CLI is new and moving, and Google's own official skill docs
are already wrong on a point this plugin cites — they say `--screen`, the binary
requires `--screenshot`. Prose about a tool ages; the only defense is asking the
binary.

    verify_tool_facts.py              # ask the installed binary
    verify_tool_facts.py --json       # same, as JSON
    verify_tool_facts.py --self-test  # does NOT touch the binary; tests the parser

IMPORTANT, and the reason --self-test never invokes `android`: the binary in
cmdline-tools/latest/bin is a bootstrapper. Any invocation, even --version,
downloads and installs hundreds of MB. On a CI runner that would be a surprise
download on every build.
"""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import tempfile
import subprocess
import sys

# (id, help argv, must contain, must not contain, what the fact supports)
FACTS = [
    ("screen-resolve-flag", ["screen", "resolve", "--help"],
     ["--screenshot"], ["--screen="],
     "SKILL.md says `android screen resolve --screenshot`; Google's skill docs "
     "say `--screen`, which the binary rejects"),
    ("screen-capture-annotate", ["screen", "capture", "--help"],
     ["--annotate"], [],
     "SKILL.md uses --annotate to see inside GL surfaces"),
    ("skills-catalog", ["skills", "--help"],
     ["add", "list"], [],
     "SKILL.md delegates teaching the CLI to `android skills add`"),
    ("docs-search", ["docs", "--help"],
     ["search"], [],
     "SKILL.md delegates documentation to `android docs search`"),
]


# The bootstrapper installs here. Reading these paths answers "which version" and
# "how many skills" without invoking anything — the contract of this file.
CLI_HOME = Path.home() / ".android" / "cli"


def installed_version(root: Path = CLI_HOME) -> str | None:
    """CLI version read from disk. Never invokes the binary."""
    f = root / "skills" / "version"
    try:
        v = f.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return v or None


def catalog_on_disk(root: Path = CLI_HOME) -> int | None:
    """How many skills Google's catalog ships, counted on disk.

    The skills cite this number with a date. Counting here makes drift visible
    without turning a changing number into a failure criterion.
    """
    d = root / "skills"
    if not d.is_dir():
        return None
    return sum(1 for _ in d.rglob("SKILL.md"))


def probe(argv: list[str]) -> str:
    """Run `android <argv>` and return stdout+stderr, or "" if unavailable."""
    exe = shutil.which("android")
    if not exe:
        return ""
    try:
        p = subprocess.run([exe, *argv], capture_output=True, text=True, timeout=120)
    except (subprocess.TimeoutExpired, OSError):
        return ""
    return (p.stdout or "") + (p.stderr or "")


# Verdict values are part of the --json output; keep them stable.
def judge(help_text: str, must: list[str], must_not: list[str]) -> tuple[str, str]:
    """Verdict on a help text. Pure: spawns no process."""
    if not help_text.strip():
        return "unavailable", "binary missing or not responding"
    missing = [t for t in must if t not in help_text]
    forbidden = [t for t in must_not if t in help_text]
    if missing:
        return "failed", f"did not find {missing} in the help"
    if forbidden:
        return "failed", f"found {forbidden}, which SKILL.md says does not exist"
    return "ok", "matches"


def run() -> int:
    # No `android --version` here: it is exactly the invocation the docstring
    # calls a surprise download, and the --self-test contract only covers what
    # is in FACTS. The resolved path answers the same question ("is there a
    # binary?") without touching the bootstrapper.
    result = {
        "android_path": shutil.which("android"),
        "android_version": installed_version(),
        "skills_catalog": catalog_on_disk(),
        "facts": [],
    }
    for fid, argv, must, must_not, supports in FACTS:
        verdict, reason = judge(probe(argv), must, must_not)
        result["facts"].append(
            {"id": fid, "verdict": verdict, "reason": reason, "supports": supports}
        )

    if "--json" in sys.argv:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        v = result["android_path"] or "android not found on PATH"
        print(f"android: {v}")
        print(f"  version (read from disk): {result['android_version'] or 'n/a'}")
        print(f"  Google catalog: {result['skills_catalog'] or 'n/a'} skills")
        for f in result["facts"]:
            mark = {"ok": "ok  ", "failed": "FAILED", "unavailable": "n/a "}[f["verdict"]]
            print(f"  {mark} {f['id']}: {f['reason']}")

    # A missing binary is not a failure: the plugin also serves machines without the SDK.
    return 1 if any(f["verdict"] == "failed" for f in result["facts"]) else 0


def self_test() -> int:
    """Test the judging without touching the binary — see the bootstrapper warning."""
    cases = [
        ("Usage: android screen resolve --screenshot=PARAM --string=PARAM",
         ["--screenshot"], ["--screen="], "ok"),
        ("Usage: android screen resolve --screen=PARAM --string=PARAM",
         ["--screenshot"], ["--screen="], "failed"),
        ("", ["--screenshot"], [], "unavailable"),
        ("   \n  ", ["--screenshot"], [], "unavailable"),
        ("Commands:\n  add\n  list\n", ["add", "list"], [], "ok"),
        ("Commands:\n  list\n", ["add", "list"], [], "failed"),
    ]
    failures = 0
    for i, (text, must, must_not, expected) in enumerate(cases, 1):
        got, reason = judge(text, must, must_not)
        if got != expected:
            print(f"case {i}: expected {expected!r}, got {got!r} ({reason})")
            failures += 1

    # The contract that protects CI: FACTS never cites an empty subcommand,
    # otherwise bare `android` is a bootstrapper waiting for input.
    for fid, argv, *_ in FACTS:
        if not argv or "--help" not in argv:
            print(f"{fid}: argv must end in --help, got {argv}")
            failures += 1

    # Disk reads: absence returns None, never an exception — the plugin serves
    # machines without the CLI, and a traceback there is worse than the missing
    # information.
    with tempfile.TemporaryDirectory() as empty:
        v = Path(empty)
        checks = [
            (installed_version(v) is None, "version: empty directory should give None"),
            (catalog_on_disk(v) is None, "catalog: no skills/ should give None"),
        ]
        (v / "skills").mkdir()
        (v / "skills" / "a").mkdir()
        (v / "skills" / "a" / "SKILL.md").write_text("x", encoding="utf-8")
        (v / "skills" / "version").write_text("  9.9.9  \n", encoding="utf-8")
        checks += [
            (catalog_on_disk(v) == 1, "catalog: did not count the SKILL.md"),
            (installed_version(v) == "9.9.9", "version: did not trim whitespace"),
        ]
        (v / "skills" / "version").write_text("", encoding="utf-8")
        checks.append(
            (installed_version(v) is None, "version: empty file should give None")
        )
        for ok, msg in checks:
            if not ok:
                print(msg)
                failures += 1

    print("self-test: ok" if not failures else f"self-test: {failures} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(self_test() if "--self-test" in sys.argv else run())
