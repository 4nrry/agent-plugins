#!/usr/bin/env python3
"""Run agent-fleet's UserPromptSubmit hook on each labeled set in logs/ and score it.

  python3 check_hook.py [path/to/inject.sh]

Each set is a JSON array of {"query", "should_trigger"}. A prompt counts as
fired when the hook prints the agent-fleet header. Stdlib only.
"""
import json, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
HOOK = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE.parents[4] / "plugins/agent-fleet/hooks/inject.sh"
if not HOOK.is_file():
    sys.exit(f"hook not found: {HOOK}")
SETS = ["dev.json", "blind-1.json", "blind-2.json", "aug-2026-08-06.json", "subagents-2026-10-28.json",
        "agent-business-nearmiss-2026-10-28.json"]

def fires(prompt: str) -> bool:
    p = subprocess.run(["bash", str(HOOK)], input=json.dumps({"prompt": prompt}),
                       capture_output=True, text=True, timeout=30)
    return "agent-fleet skill applies" in p.stdout

for name in SETS:
    data = json.loads((HERE / "logs" / name).read_text(encoding="utf-8"))
    tp = fn = fp = tn = 0
    for d in data:
        hit = fires(d["query"])
        if d["should_trigger"]:
            tp, fn = (tp + 1, fn) if hit else (tp, fn + 1)
        else:
            fp, tn = (fp + 1, tn) if hit else (fp, tn + 1)
        if hit != d["should_trigger"]:
            print(f"  {'MISS ' if d['should_trigger'] else 'FALSE'} {name}: {d['query'][:80]}")
    print(f"{name:22s} fired {tp}/{tp + fn} should-trigger, {fp}/{fp + tn} near-misses")
