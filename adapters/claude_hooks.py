#!/usr/bin/env python3
"""Run this marketplace's portable plugins' Claude Code hooks for one event.

  claude_hooks.py EVENT [--plugin NAME]... [--json] < payload.json

For tools whose own hooks speak Claude Code's contract (Kimi Code, Muse, ZCode:
snake_case JSON on stdin, exit 2 blocks with the reason on stderr, stdout
becomes context): register one hook per event that runs this script, and it runs every
matching command from the plugins' hooks/hooks.json in the marketplace clone,
with CLAUDE_PLUGIN_ROOT set. Matchers are checked here against `tool_name`,
after mapping the tool's own name (bash, exec_command) to Claude's.
Output: exit 2 and the reason on stderr when any hook blocks; otherwise the
joined context on stdout. Inside a crew worker run (CREW_RUN) it does nothing.

Without --plugin, a plugin runs only when adapters/global-plugins.json lists it
or the payload's cwd (or a parent below home) links one of its skills in
.agents/skills, as the bridges decide. --plugin NAME runs only the named
plugins, for a per-project hook file written by scripts/project_tools.py.
--json prints the context as Claude's hookSpecificOutput.additionalContext, for
tools that read only JSON from a hook (Grok). The payload may use Grok's
camelCase keys (toolName, toolInput); an MCP tool named `server__tool` or
`mcp__server__tool` is matched under Claude's plugin name for it.
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
ALIASES = {"path": "file_path", "filePath": "file_path", "cmd": "command"}
# Other tools' names (lowercased) for Claude Code's tools.
TOOL_NAMES = {"bash": "Bash", "shell": "Bash", "exec_command": "Bash", "run_terminal_command": "Bash",
              "read": "Read", "read_file": "Read", "write": "Write", "write_file": "Write", "edit": "Edit",
              "glob": "Glob", "grep": "Grep"}


def plugins() -> list:
    root = MARKETPLACE / "plugins"
    return sorted(p for p in root.iterdir() if (p / "plugin.json").is_file()) if root.is_dir() else []


def global_names():
    """Names in adapters/global-plugins.json; None (every plugin) if unreadable."""
    try:
        names = json.loads((MARKETPLACE / "adapters" / "global-plugins.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return set(names) if isinstance(names, list) and all(isinstance(n, str) for n in names) else None


def project_names(start: Path) -> set:
    """Plugins whose skills are linked into .agents/skills of start or a parent below home."""
    names, home = set(), Path.home().resolve()
    for folder in (start, *start.parents):
        if home not in folder.parents:
            break
        try:
            entries = list((folder / ".agents" / "skills").iterdir())
        except OSError:
            continue
        for entry in entries:
            try:
                parts = Path(os.readlink(entry)).parts
            except OSError:
                continue
            hits = [i for i, part in enumerate(parts) if part == "plugins"]
            if hits and hits[-1] + 1 < len(parts):
                names.add(parts[hits[-1] + 1])
    return names


def active(only: list, cwd) -> list:
    every = plugins()
    if only:
        return [p for p in every if p.name in only]
    names = global_names()
    if names is None:
        return every
    start = Path(os.path.expanduser(cwd)) if isinstance(cwd, str) and cwd else Path.cwd()
    names |= project_names(start.resolve())
    return [p for p in every if p.name in names]


def mcp_servers(plugin: Path) -> set:
    try:
        return set(json.loads((plugin / "mcp.json").read_text(encoding="utf-8")).get("mcpServers", {}))
    except (OSError, ValueError, AttributeError):
        return set()


def plugin_tool(plugin: Path, tool: str) -> str:
    """`kinocut__video_info` or `mcp__kinocut__video_info` -> Claude's `mcp__plugin_<p>_kinocut__video_info`."""
    bare = tool[len("mcp__"):] if tool.startswith("mcp__") else tool
    server, sep, rest = bare.partition("__")
    if sep and server in mcp_servers(plugin):
        return f"mcp__plugin_{plugin.name}_{server}__{rest}"
    return tool


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


def dispatch(event: str, payload: dict, only=None) -> tuple:
    """(exit code, stdout, stderr) for one event."""
    payload = dict(payload)
    for camel, snake in (("toolName", "tool_name"), ("toolInput", "tool_input")):
        if camel in payload and snake not in payload:
            payload[snake] = payload[camel]
    tool = str(payload.get("tool_name", ""))
    payload["tool_name"] = TOOL_NAMES.get(tool.lower(), tool)
    tool_input = payload.get("tool_input")
    if isinstance(tool_input, dict):
        tool_input = {ALIASES.get(k, k): v for k, v in tool_input.items()}
        if isinstance(tool_input.get("command"), list):
            tool_input["command"] = " ".join(map(str, tool_input["command"]))
        payload["tool_input"] = tool_input
    payload.setdefault("hook_event_name", event)
    contexts = []
    for plugin in active(only or [], payload.get("cwd")):
        tool_name = plugin_tool(plugin, str(payload.get("tool_name", "")))
        for matcher, command in hooks(plugin, event):
            if event in ("PreToolUse", "PostToolUse") and not matches(matcher, tool_name):
                continue
            r = run(command, plugin, dict(payload, tool_name=tool_name))
            if r.get("block"):
                return 2, "", r["block"]
            if r.get("context"):
                contexts.append(r["context"])
    return 0, "\n\n".join(contexts), ""


def self_test() -> int:
    code, out, _ = dispatch("UserPromptSubmit", {"prompt": "ask grok and codex"}, ["crew"])
    assert code == 0 and "crew skill may apply" in out, out
    code, out, _ = dispatch("PreToolUse", {"tool_name": "Bash", "tool_input": {"command": "vipsthumbnail a.jpg -o b.png"}},
                            ["media-agent"])
    assert code == 0 and "vipsthumbnail -o NAME" in out, out
    code, out, _ = dispatch("PreToolUse", {"tool_name": "exec_command", "tool_input": {"cmd": "vipsthumbnail a.jpg -o b.png"}},
                            ["media-agent"])
    assert code == 0 and "vipsthumbnail -o NAME" in out, out
    code, out, _ = dispatch("PreToolUse", {"toolName": "run_terminal_command",
                                           "toolInput": {"command": "vipsthumbnail a.jpg -o b.png"}}, ["media-agent"])
    assert code == 0 and "vipsthumbnail -o NAME" in out, out
    code, out, _ = dispatch("PreToolUse", {"tool_name": "Read", "tool_input": {"path": "x"}}, ["media-agent"])
    assert code == 0 and out == "", out
    plugin = MARKETPLACE / "plugins" / "media-agent"
    for name in ("kinocut__video_info", "mcp__kinocut__video_info"):
        assert plugin_tool(plugin, name) == "mcp__plugin_media-agent_kinocut__video_info", name
    assert plugin_tool(plugin, "other__x") == "other__x"
    # Outside any project, only the global list runs: no media-agent warning in /.
    names = global_names()
    if names is not None and "media-agent" not in names:
        code, out, _ = dispatch("PreToolUse", {"tool_name": "Bash", "cwd": "/",
                                               "tool_input": {"command": "vipsthumbnail a.jpg -o b.png"}})
        assert code == 0 and "vipsthumbnail -o NAME" not in out, out
    print("self-test: ok")
    return 0


def main() -> int:
    args = sys.argv[1:]
    if args == ["--self-test"]:
        return self_test()
    as_json = "--json" in args
    args = [a for a in args if a != "--json"]
    only = []
    while "--plugin" in args:
        i = args.index("--plugin")
        if i + 1 >= len(args):
            sys.exit(__doc__.strip().splitlines()[2])
        only.append(args[i + 1])
        del args[i:i + 2]
    if len(args) != 1:
        sys.exit(__doc__.strip().splitlines()[2])
    if os.environ.get("CREW_RUN"):
        return 0
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except ValueError:
        return 0
    code, out, err = dispatch(args[0], payload if isinstance(payload, dict) else {}, only)
    if out and as_json:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": args[0], "additionalContext": out}}))
    elif out:
        print(out)
    if err:
        print(err, file=sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main())
