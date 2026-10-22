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

PLUGIN_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

prompt=$(jq -r '.prompt // empty' 2>/dev/null) || exit 0
[[ -n "$prompt" ]] || exit 0

matched=()
for backend in agy opencode copilot codex grok hermes kimi muse; do
  if printf '%s' "$prompt" | grep -qiwF -- "$backend"; then
    matched+=("$backend")
  fi
done
(( ${#matched[@]} )) || exit 0

refs=""
for backend in "${matched[@]}"; do
  [[ -f "$PLUGIN_ROOT/references/$backend.md" ]] && refs+=" $PLUGIN_ROOT/references/$backend.md"
done
printf 'The crew skill may apply (matched: %s). Before using another agent CLI as a worker, read %s/SKILL.md%s. crew.py is %s/scripts/crew.py.\n' \
  "${matched[*]}" "$PLUGIN_ROOT" "${refs:+ and, for delegate,$refs}" "$PLUGIN_ROOT"
exit 0
