#!/usr/bin/env python3
"""Run this marketplace's portable plugins' Claude Code hooks for one event.

  claude_hooks.py EVENT < payload.json

For tools whose own hooks speak Claude Code's contract (Kimi Code: snake_case
JSON on stdin, exit 2 blocks with the reason on stderr, stdout becomes
context): register one hook per event that runs this script, and it runs every
matching command from the plugins' hooks/hooks.json in the marketplace clone,
with CLAUDE_PLUGIN_ROOT set. Matchers are checked here against `tool_name`.
Output: exit 2 and the reason on stderr when any hook blocks; otherwise the
joined context on stdout. Inside a crew worker run (CREW_RUN) it does nothing.
Stdlib only.
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

MARKETPLACE = Path(__file__).resolve().parent.parent
HOOK_TIMEOUT_S = 30
# Argument names other tools use where Claude Code's hook scripts read another.
ALIASES = {"path": "file_path", "filePath": "file_path"}


def plugins() -> list:
    root = MARKETPLACE / "plugins"
    return sorted(p for p in root.iterdir() if (p / "plugin.json").is_file()) if root.is_dir() else []


def hooks(plugin: Path, event: str) -> list:
    try:
        spec = json.loads((plugin / "hooks" / "hooks.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [(group.get("matcher"), h["command"])
            for group in spec.get("hooks", {}).get(event, [])
            for h in group.get("hooks", []) if h.get("type") == "command"]


def matches(matcher, tool: str) -> bool:
    if not matcher or matcher == "*":
        return True
    try:
        return re.fullmatch(matcher, tool) is not None
    except re.error:
        return matcher == tool


def run(command: str, root: Path, payload: dict) -> dict:
    try:
        p = subprocess.run(["bash", "-c", command], input=json.dumps(payload), capture_output=True, text=True,
                           timeout=HOOK_TIMEOUT_S, env={**os.environ, "CLAUDE_PLUGIN_ROOT": str(root)})
    except (OSError, subprocess.TimeoutExpired):
        return {}
    if p.returncode == 2:
        return {"block": (p.stderr or "blocked by a hook").strip()}
    out = p.stdout.strip()
    try:
        data = json.loads(out) if out.startswith("{") else None
    except ValueError:
        data = None
    if data is None:
        return {"context": out}
    specific = data.get("hookSpecificOutput") or {}
    if specific.get("permissionDecision") == "deny" or data.get("decision") == "block":
        return {"block": specific.get("permissionDecisionReason") or data.get("reason") or "blocked by a hook"}
    return {"context": specific.get("additionalContext") or data.get("additionalContext") or ""}


def dispatch(event: str, payload: dict) -> tuple:
    """(exit code, stdout, stderr) for one event."""
    tool_input = payload.get("tool_input")
    if isinstance(tool_input, dict):
        payload = dict(payload, tool_input={ALIASES.get(k, k): v for k, v in tool_input.items()})
    payload.setdefault("hook_event_name", event)
    contexts = []
    for plugin in plugins():
        for matcher, command in hooks(plugin, event):
            if event in ("PreToolUse", "PostToolUse") and not matches(matcher, str(payload.get("tool_name", ""))):
                continue
            r = run(command, plugin, payload)
            if r.get("block"):
                return 2, "", r["block"]
            if r.get("context"):
                contexts.append(r["context"])
    return 0, "\n\n".join(contexts), ""


def self_test() -> int:
    code, out, _ = dispatch("UserPromptSubmit", {"prompt": "ask grok and codex"})
    assert code == 0 and "crew skill may apply" in out, out
    code, out, _ = dispatch("PreToolUse", {"tool_name": "Bash", "tool_input": {"command": "vipsthumbnail a.jpg -o b.png"}})
    assert code == 0 and "vipsthumbnail -o NAME" in out, out
    code, out, _ = dispatch("PreToolUse", {"tool_name": "Read", "tool_input": {"path": "x"}})
    assert code == 0 and out == "", out
    print("self-test: ok")
    return 0


def main() -> int:
    if sys.argv[1:] == ["--self-test"]:
        return self_test()
    if len(sys.argv) != 2:
        sys.exit(__doc__.strip().splitlines()[2])
    if os.environ.get("CREW_RUN"):
        return 0
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except ValueError:
        return 0
    code, out, err = dispatch(sys.argv[1], payload if isinstance(payload, dict) else {})
    if out:
        print(out)
    if err:
        print(err, file=sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main())
