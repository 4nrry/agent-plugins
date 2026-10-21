#!/usr/bin/env bash
# UserPromptSubmit: when the prompt names an installed game, inject what the
# machine knows about it (appid, buildid, last update, patch-notes URL).
#
# A hook, not a description: in this repo's agent-fleet trigger eval a skill
# description fired on 2 of 30 should-trigger runs
# (bench/plugins/agent-fleet/results/2026-08-06-trigger-eval/). Matching lives in
# the Python detector, which the self-test covers; this script only forwards
# the prompt. Firing rate and false positives of this hook are not measured.
#
# Fails open, always exit 0: a missing hint costs less than a blocked prompt.
set -uo pipefail

# Resolved from this file's location, so it works from the hook runner, by
# hand, or from a copied tree.
PLUGIN_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DETECTOR="$PLUGIN_ROOT/skills/game-versions/scripts/steam_games.py"

command -v jq >/dev/null 2>&1 || exit 0
command -v python3 >/dev/null 2>&1 || exit 0

prompt=$(jq -r '.prompt // empty' 2>/dev/null) || exit 0
[[ -n "$prompt" ]] || exit 0

if [[ ! -x "$DETECTOR" ]]; then
  echo "game-facts: $DETECTOR missing or not executable; nothing injected" >&2
  exit 0
fi

out=$(printf '%s' "$prompt" | python3 "$DETECTOR" --match-stdin 2>/dev/null) || exit 0
[[ -n "$out" ]] || exit 0

printf '%s\nSkill: %s/skills/game-versions/SKILL.md\n' "$out" "$PLUGIN_ROOT"
exit 0
