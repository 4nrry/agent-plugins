#!/usr/bin/env bash
# UserPromptSubmit hook: when the prompt names a crew backend as a whole word
# (case-insensitive), add one line pointing at crew's SKILL.md, the backend's
# reference file if it has one, and the real path of crew.py. Advisory only:
# it never blocks, always exits 0, reads only the prompt, no network.
#
# Why a hook and not the skill description alone: agent-fleet measured
# description triggering at 2 of 30 should-trigger runs (trigger-eval
# 2026-08-06, bench/plugins/agent-fleet/results/2026-08-06-trigger-eval/ in
# https://github.com/4nrry/agent-plugins). This hook's own hit rate is
# unmeasured. "claude" and "cursor" are left out: they name the host or an
# editor far more often than a worker.
set -euo pipefail

# The skill lives in skills/crew/ (the Agent Plugins layout).
SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../skills/crew" && pwd)"

command -v jq >/dev/null || { echo "crew inject hook: jq not found, no pointer added" >&2; exit 0; }
# Only the user's words are matched. The host puts its own blocks into the same
# prompt field: CLAUDE.md and other <system-reminder>s, background-subagent
# <task-notification>s, messages from other sessions. Matching them fired the
# agent-fleet hook on prompts that never mentioned an agent (2026-11-22), and
# a backend name inside a reminder or a task-notification would fire this one. Blocks
# are removed whole, tag to closing tag; an unclosed tag is left alone, so a
# user who types the tag name is still read. A prompt that is nothing but such
# blocks matches nothing.
# More than 100 opening tags is not a conversation: the lazy match rescans to the
# end for each tag that never closes, which took 12 s on 8,000 of them, so such
# a prompt is treated as matching nothing.
TAGS='system-reminder|task-notification|cross-session-message|side-sessions-event|local-command-caveat|local-command-stdout|local-command-stderr|user-prompt-submit-hook|command-name|command-message|command-args|ide_opened_file|ide_selection|ide_diagnostics'
prompt=$(jq -r --arg tags "$TAGS" '
  (.prompt // empty) | if type != "string" then empty
  elif ([match("<(" + $tags + ")[\\s>]"; "g")] | length) > 100 then empty
  else gsub("<(?<t>" + $tags + ")(\\s[^>]*)?>[\\s\\S]*?</\\k<t>>"; "") end' \
  2>/dev/null) || exit 0
[[ "$prompt" =~ [^[:space:]] ]] || exit 0

matched=()
for backend in agy opencode copilot codex grok hermes kimi muse; do
  # A here-string, not a pipe: with pipefail, grep -q leaving at its first
  # match kills the writer and a long prompt reads as "no match".
  if grep -qiwF -- "$backend" <<<"$prompt"; then
    matched+=("$backend")
  fi
done
(( ${#matched[@]} )) || exit 0

refs=""
for backend in "${matched[@]}"; do
  [[ -f "$SKILL_DIR/references/$backend.md" ]] && refs+=" $SKILL_DIR/references/$backend.md"
done
printf 'The crew skill may apply (matched: %s). Before using another agent CLI as a worker, read %s/SKILL.md%s. crew.py is %s/scripts/crew.py.\n' \
  "${matched[*]}" "$SKILL_DIR" "${refs:+ and, for delegate,$refs}" "$SKILL_DIR"
exit 0
