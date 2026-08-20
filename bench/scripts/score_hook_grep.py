#!/usr/bin/env python3
"""Score the agent-fleet UserPromptSubmit hook against a frozen eval set.

The apparatus is the hook itself: this runs `hooks/inject.sh` as the harness
runs it — the eval item's `input` is handed over on stdin as {"prompt": ...},
and "fired" means the script wrote anything to stdout. No model is in the
loop, so every outcome here is a script measurement, and re-running on the
same eval file must reproduce byte-identical counts.

Ways this check silently fails, each of which turns a real hook behaviour into
a wrong number:

1. `jq` missing. The hook parses stdin with jq and `exit 0`s when it is
   absent, so every item scores as silent and the run looks like perfect
   precision. Checked at startup; the script refuses to run without it.
2. Wrong hook path. A stale or copied inject.sh scores a matcher that is not
   the shipped one. The resolved path and its sha256 are printed and belong
   in the run record.
3. stderr counted as firing. The hook writes a diagnostic to stderr when
   SKILL.md is missing and still exits non-zero; only stdout means fired.
4. Shell interpolation. Prompts carry quotes, pipes and newlines; they are
   passed as JSON on stdin, never through a shell string.
5. Trailing-newline drift. `printf` vs `echo` changes stdout by one byte and
   not the verdict — emptiness is tested after strip().
6. Locale. The hook greps case-insensitively over UTF-8 prompts; LC_ALL=C is
   forced so the match does not depend on the caller's environment.
7. A self-test that only proves one end. A matcher that fires on everything
   and one that fires on nothing both pass a single-case test, so --self-test
   asserts a known fire AND a known silence before any item is scored.
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HOOK = os.path.join(REPO, "plugins", "agent-fleet", "hooks", "inject.sh")

# Known-answer pairs for --self-test: one must fire, one must stay silent.
# Proving both ends is the point; a fire-on-everything matcher passes either
# one alone.
SELF_TEST = [("ultracode: do the thing", True), ("what time is it in Lisbon", False)]


def run_hook(prompt: str) -> tuple[bool, str]:
    """Return (fired, stderr). Fired means non-empty stdout."""
    env = dict(os.environ, LC_ALL="C")
    proc = subprocess.run(
        ["bash", HOOK],
        input=json.dumps({"prompt": prompt}),
        capture_output=True,
        text=True,
        env=env,
    )
    return bool(proc.stdout.strip()), proc.stderr.strip()


def preflight() -> str:
    if not shutil.which("jq"):
        sys.exit("FAIL: jq not on PATH — the hook would exit 0 on every prompt "
                 "and this run would report false silence.")
    if not os.path.isfile(HOOK):
        sys.exit(f"FAIL: hook not found at {HOOK}")
    with open(HOOK, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def self_test() -> None:
    for prompt, want in SELF_TEST:
        got, err = run_hook(prompt)
        if got != want:
            sys.exit(f"FAIL self-test: {prompt!r} expected fired={want}, got {got}"
                     + (f" (stderr: {err})" if err else ""))
    print("self-test OK: fires on a known trigger, silent on a known non-trigger")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("eval_file", nargs="?")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--json", action="store_true", help="emit per-item results as JSON")
    args = ap.parse_args()

    hook_sha = preflight()
    self_test()
    if args.self_test and not args.eval_file:
        return 0
    if not args.eval_file:
        ap.error("eval_file required unless --self-test is used alone")

    with open(args.eval_file, "rb") as fh:
        raw = fh.read()
    eval_sha = hashlib.sha256(raw).hexdigest()
    items = json.loads(raw)["items"]

    results = []
    for item in items:
        fired, err = run_hook(item["input"])
        should = item["class"] == "invocation"
        results.append({
            "id": item["id"],
            "class": item["class"],
            "should_fire": should,
            "fired": fired,
            "correct": fired == should,
            "stderr": err or None,
        })

    fires = [r for r in results if r["class"] == "invocation"]
    mentions = [r for r in results if r["class"] == "mention"]
    summary = {
        "hook_sha256": hook_sha,
        "eval_sha256": eval_sha,
        "invocation_fired": sum(r["fired"] for r in fires),
        "invocation_total": len(fires),
        "mention_fired": sum(r["fired"] for r in mentions),
        "mention_total": len(mentions),
    }

    if args.json:
        print(json.dumps({"summary": summary, "items": results}, indent=2))
    else:
        print(f"\nhook   {hook_sha[:12]}…\neval   {eval_sha[:12]}…\n")
        for r in results:
            mark = "ok " if r["correct"] else "MISS"
            print(f"  {mark} item {r['id']:>2}  {r['class']:<10} "
                  f"should_fire={str(r['should_fire']):<5} fired={r['fired']}")
        print(f"\ninvocation fired {summary['invocation_fired']}/{summary['invocation_total']}"
              f"   mention fired {summary['mention_fired']}/{summary['mention_total']}"
              " (mention fires are false fires by the hook's stated intent)")

    # Exit code reports whether the hook matched intent, not whether the script ran.
    return 0 if all(r["correct"] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
