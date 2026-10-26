"""Hermes plugin: runs the Claude Code hooks of this marketplace's portable
plugins (those with an Agent Plugins plugin.json) inside Hermes, from the same
hooks/hooks.json files Claude Code uses. link_skills.py links this folder into
~/.hermes/plugins/; enable it once with `hermes plugins enable 4nrry-bridge`.

Mapping (Claude hook contract -> Hermes plugin hooks):
  UserPromptSubmit -> pre_llm_call: run with {"prompt": message}; its stdout (or
                      additionalContext) is appended to the turn's user message.
  PreToolUse       -> pre_tool_call: run with {"tool_name", "tool_input"} in
                      Claude's names; a deny (or exit 2) blocks the call; other
                      context is appended to that tool's result through
                      transform_tool_result.
Other events, and matchers for tools Hermes lacks (Workflow), are skipped.
Inside a crew worker run (CREW_RUN set) the bridge does nothing.
"""
import json
import os
import re
import subprocess
from pathlib import Path

MARKETPLACE = Path(os.environ.get("AGENT_PLUGINS_MARKETPLACE",
                                  Path.home() / ".claude/plugins/marketplaces/4nrry"))
HOOK_TIMEOUT_S = 30
# Hermes tool -> (Claude tool, {Hermes arg: Claude arg})
TOOLS = {
    "terminal": ("Bash", {"command": "command", "workdir": "cwd"}),
    "read_file": ("Read", {"path": "file_path"}),
    "write_file": ("Write", {"path": "file_path", "content": "content"}),
    "patch": ("Edit", {"path": "file_path", "old_string": "old_string", "new_string": "new_string"}),
    "search_files": ("Grep", {"pattern": "pattern", "path": "path"}),
}


def _plugins() -> list:
    root = MARKETPLACE / "plugins"
    return sorted(p for p in root.iterdir() if (p / "plugin.json").is_file()) if root.is_dir() else []


def _hooks(plugin: Path, event: str) -> list:
    try:
        spec = json.loads((plugin / "hooks" / "hooks.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [(group.get("matcher"), h["command"], plugin)
            for group in spec.get("hooks", {}).get(event, [])
            for h in group.get("hooks", []) if h.get("type") == "command"]


def _matches(matcher, tool: str) -> bool:
    if not matcher or matcher == "*":
        return True
    try:
        return re.fullmatch(matcher, tool) is not None
    except re.error:
        return matcher == tool


def _run(command: str, root: Path, payload: dict) -> dict:
    """One hook command -> {"block", "reason", "context"}."""
    try:
        p = subprocess.run(["bash", "-c", command], input=json.dumps(payload), capture_output=True,
                           text=True, timeout=HOOK_TIMEOUT_S, env={**os.environ, "CLAUDE_PLUGIN_ROOT": str(root)})
    except (OSError, subprocess.TimeoutExpired):
        return {}
    if p.returncode == 2:
        return {"block": True, "reason": (p.stderr or "blocked by a hook").strip()}
    out = p.stdout.strip()
    if not out:
        return {}
    try:
        data = json.loads(out)
    except ValueError:
        return {"context": out}
    specific = data.get("hookSpecificOutput") or {}
    if specific.get("permissionDecision") == "deny" or data.get("decision") == "block":
        return {"block": True,
                "reason": specific.get("permissionDecisionReason") or data.get("reason") or "blocked by a hook"}
    return {"context": specific.get("additionalContext") or data.get("additionalContext") or ""}


def _text(message) -> str:
    if isinstance(message, str):
        return message
    return " ".join(part.get("text", "") for part in message or [] if isinstance(part, dict))


def register(ctx):
    if os.environ.get("CREW_RUN"):
        return
    plugins = _plugins()
    pending = {}  # (task_id, tool_name) -> [context]

    def pre_llm_call(session_id="", user_message="", **_):
        texts = [_run(cmd, root, {"hook_event_name": "UserPromptSubmit", "prompt": _text(user_message),
                                  "session_id": session_id}).get("context")
                 for plugin in plugins for _m, cmd, root in _hooks(plugin, "UserPromptSubmit")]
        joined = "\n\n".join(t for t in texts if t)
        return {"context": joined} if joined else None

    def pre_tool_call(tool_name="", args=None, task_id="", **_):
        claude_tool, keys = TOOLS.get(tool_name, (None, {}))
        if not claude_tool:
            return None
        tool_input = {keys.get(k, k): v for k, v in (args or {}).items()}
        for plugin in plugins:
            for matcher, cmd, root in _hooks(plugin, "PreToolUse"):
                if not _matches(matcher, claude_tool):
                    continue
                r = _run(cmd, root, {"hook_event_name": "PreToolUse", "tool_name": claude_tool,
                                     "tool_input": tool_input})
                if r.get("block"):
                    return {"action": "block", "message": r["reason"]}
                if r.get("context"):
                    pending.setdefault((task_id, tool_name), []).append(r["context"])
        return None

    def transform_tool_result(tool_name="", result="", task_id="", **_):
        notes = pending.pop((task_id, tool_name), None)
        return f"{result}\n\n[hook] " + "\n[hook] ".join(notes) if notes else None

    ctx.register_hook("pre_llm_call", pre_llm_call)
    ctx.register_hook("pre_tool_call", pre_tool_call)
    ctx.register_hook("transform_tool_result", transform_tool_result)
