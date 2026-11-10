#!/usr/bin/env python3
"""Fixture test for plugins/agent-fleet/hooks/check-routing.sh.

  check_routing_hook.py --self-test

Pipes sample PreToolUse JSON into the hook and checks what it prints: a deny
for an unrouted script (once), for another workflow invoked by name (once) and
for the bare built-in name (every time); nothing for a routed script, the
plugin's own fork, a resume or input it cannot parse. The hook always exits 0.
Needs bash, jq and sha256sum; without one it reports a skip, since the hook
then does nothing.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HOOK = Path(__file__).resolve().parents[4] / "plugins/agent-fleet/hooks/check-routing.sh"
ROUTED = "await agent('a', {model: 'haiku'})\nawait agent('b', {\n  model: 'sonnet',\n})\n"
UNROUTED = "// model: mentioned in a comment only\nawait agent('a')\nawait agent('b', {model: 'haiku'})\n"
NO_AGENTS = "const x = 1\n"


def run(payload, data_dir):
    stdin = payload if isinstance(payload, str) else json.dumps(payload)
    p = subprocess.run(["bash", str(HOOK)], input=stdin, capture_output=True, text=True, timeout=30,
                       env={**os.environ, "CLAUDE_PLUGIN_DATA": data_dir})
    decision = None
    if p.stdout.strip():
        decision = json.loads(p.stdout)["hookSpecificOutput"]["permissionDecision"]
    return p.returncode, decision


def self_test():
    missing = [t for t in ("jq", "sha256sum") if not shutil.which(t)]
    if missing:
        print(f"self-test skipped: {', '.join(missing)} not installed, and without it the hook does nothing")
        return 0
    fails = []
    with tempfile.TemporaryDirectory() as tmp:
        data = str(Path(tmp, "data"))
        script_file = Path(tmp, "wf.js")
        script_file.write_text(UNROUTED.replace("'a'", "'from a file'"), encoding="utf-8")
        call = lambda **tool_input: {"tool_name": "Workflow", "tool_input": tool_input}  # noqa: E731
        cases = [
            ("a routed script passes", call(script=ROUTED), None),
            ("a script with no agent() passes", call(script=NO_AGENTS), None),
            ("an unrouted script is denied", call(script=UNROUTED), "deny"),
            ("the same unrouted script passes the second time", call(script=UNROUTED), None),
            ("an unrouted scriptPath is denied", call(scriptPath=str(script_file)), "deny"),
            ("the bare built-in name is denied", call(name="deep-research"), "deny"),
            ("the bare built-in name is denied again", call(name="deep-research"), "deny"),
            ("the plugin's routed fork passes", call(name="agent-fleet:deep-research"), None),
            ("another workflow by name is denied once", call(name="other:flow"), "deny"),
            ("the same name passes the second time", call(name="other:flow"), None),
            ("a resume passes", call(script=UNROUTED + "// v2\n", resumeFromRunId="wf_abc123"), None),
            ("input that is not JSON passes", "not json", None),
            ("a call with no tool_input passes", {"tool_name": "Workflow"}, None),
        ]
        for label, payload, want in cases:
            try:
                code, got = run(payload, data)
            except (ValueError, KeyError, subprocess.TimeoutExpired) as e:
                fails.append(f"{label}: {e!r}")
                continue
            if code != 0 or got != want:
                fails.append(f"{label}: exit {code}, decision {got!r}, expected exit 0 and {want!r}")
    for f in fails:
        print("FAIL:", f)
    print(f"self-test: {'ok' if not fails else str(len(fails)) + ' failed'}")
    return 1 if fails else 0


if __name__ == "__main__":
    if "--self-test" not in sys.argv[1:]:
        sys.exit(__doc__)
    sys.exit(self_test())
