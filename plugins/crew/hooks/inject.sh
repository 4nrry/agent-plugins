#!/usr/bin/env bash
# UserPromptSubmit hook: when the prompt names agy, opencode or copilot as a
# whole word (case-insensitive), inject that backend's SKILL.md plus a line
# pointing at the delegate skill and the real path of crew.py. Advisory only: it never blocks, always
# exits 0, reads only the prompt and files in this plugin, no network.
#
# Why a hook and not the skill descriptions: agent-fleet measured description
# triggering at 2 of 30 should-trigger runs (trigger-eval 2026-08-06,
# bench/plugins/agent-fleet/results/2026-08-06-trigger-eval/ in
# https://github.com/4nrry/agent-plugins). This hook's own hit rate is
# unmeasured. Whole-word match: "agy-worker" and "crew:agy" match, "agyx" not.
set -euo pipefail

PLUGIN_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

prompt=$(jq -r '.prompt // empty' 2>/dev/null) || exit 0
[[ -n "$prompt" ]] || exit 0

matched=()
for backend in agy opencode copilot; do
  if printf '%s' "$prompt" | grep -qiwF -- "$backend"; then
    matched+=("$backend")
  fi
done
(( ${#matched[@]} )) || exit 0

for backend in "${matched[@]}"; do
  skill="$PLUGIN_ROOT/skills/$backend/SKILL.md"
  if [[ ! -f "$skill" ]]; then
    echo "crew plugin hook: $skill not found; skill not injected" >&2
    continue
  fi
  printf 'The crew:%s skill applies to this request (matched the word "%s"). Read %s/skills/delegate/SKILL.md before delegating or reviewing through it. In both skills, scripts/crew.py is %s/skills/delegate/scripts/crew.py.\n\n' \
    "$backend" "$backend" "$PLUGIN_ROOT" "$PLUGIN_ROOT"
  cat "$skill"
  printf '\n'
done
exit 0
