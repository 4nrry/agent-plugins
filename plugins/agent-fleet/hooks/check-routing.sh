#!/usr/bin/env bash
# PreToolUse hook on the Workflow tool: the routing audit as mechanism, at
# the moment of dispatch. Exists because the prose rule alone failed in
# production — a predefined deep-research run reached ~97 agents all
# inheriting the session's top-tier model with the rule loaded in context.
#
# Behavior: denies ONCE per distinct unrouted script (or per predefined
# workflow name), with the routing instruction as the reason; an identical
# re-invocation passes, because re-invoking after reading the reason IS the
# acknowledgment. Two exceptions on the name path: bare 'deep-research' is
# denied EVERY time — this plugin ships the routed fork, registered as
# 'agent-fleet:deep-research', so the bare name can only mean the unrouted
# built-in — and 'agent-fleet:deep-research' passes silently, because its
# script carries the per-phase overrides. Resume calls, scripts with model:
# overrides, and scripts with no agent() calls pass silently. Any parse
# failure passes silently — a broken check must never block work.
set -euo pipefail

input=$(cat)
tool_input=$(jq -c '.tool_input // empty' <<<"$input" 2>/dev/null) || exit 0
[[ -n "$tool_input" ]] || exit 0

# Resume is never obstructed — it is also the recommended late fix
# (stop, edit overrides, resume; the unchanged prefix replays from cache).
jq -e '.resumeFromRunId // empty' <<<"$tool_input" >/dev/null 2>&1 && exit 0

DATA="${CLAUDE_PLUGIN_DATA:-$HOME/.claude/plugins/data/agent-fleet-routing}"
mkdir -p "$DATA" 2>/dev/null || exit 0

deny() {
  jq -cn --arg r "$1" \
    '{hookSpecificOutput: {hookEventName: "PreToolUse", permissionDecision: "deny", permissionDecisionReason: $r}}'
  exit 0
}

script=$(jq -r '.script // empty' <<<"$tool_input")
if [[ -z "$script" ]]; then
  sp=$(jq -r '.scriptPath // empty' <<<"$tool_input")
  [[ -n "$sp" && -r "$sp" ]] && script=$(cat "$sp")
fi

if [[ -n "$script" ]]; then
  agents=$(grep -c 'agent(' <<<"$script" || true)
  [[ "$agents" -eq 0 ]] && exit 0
  grep -q 'model:' <<<"$script" && exit 0
  sha=$(LC_ALL=C sha256sum <<<"$script" | cut -d' ' -f1)
  marker="$DATA/ack-script-$sha"
  [[ -e "$marker" ]] && exit 0
  touch "$marker"
  deny "agent-fleet routing check (fires once per script): this workflow script has $agents agent() call line(s) and no 'model:' override, so every agent inherits the session model, at fan-out scale. Read the script and add per-phase overrides — long tool loops on a small model, adversarial verification on a mid model — or, if inheritance is intended, re-invoke unchanged: this check will not fire again for this exact script."
fi

name=$(jq -r '.name // empty' <<<"$tool_input")
if [[ -n "$name" ]]; then
  # The bare built-in name is a standing trap wherever this plugin is
  # installed: the routed fork registers as 'agent-fleet:deep-research', so
  # name: "deep-research" can only dispatch the unrouted built-in. Deny every
  # time, no acknowledgment marker — the 2026-08-28 incident was exactly an
  # acknowledged bare-name dispatch, a full fan-out on the session model.
  if [[ "$name" == "deep-research" ]]; then
    deny "agent-fleet routing check (fires every time): Workflow({name: \"deep-research\"}) dispatches the UNROUTED built-in — every agent inherits the session model, at fan-out scale. This plugin ships a routed fork registered as 'agent-fleet:deep-research' (search/fetch on haiku, verify on sonnet): re-invoke with that name, passing the same args. If the unrouted built-in is genuinely intended, dispatch its script via script/scriptPath, where the once-per-script acknowledgment applies."
  fi
  # The plugin's own fork needs no dispatch-time audit: its script carries
  # the per-phase model: overrides (workflows/deep-research.js).
  [[ "$name" == "agent-fleet:deep-research" ]] && exit 0
  safe=$(printf '%s' "$name" | tr -c 'A-Za-z0-9._-' '_')
  marker="$DATA/ack-name-$safe"
  [[ -e "$marker" ]] && exit 0
  touch "$marker"
  deny "agent-fleet routing check (fires once per workflow name): '$name' is a predefined workflow whose script this hook cannot read from the tool call. In the one measured failure, a predefined deep-research run reached ~97 agents all inheriting the session's top-tier model because nothing routed its phases. Locate and read its script if you can and add model: overrides; to proceed as-is, re-invoke — this check will not fire again for '$name'."
fi

exit 0
