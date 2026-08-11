#!/usr/bin/env bash
# UserPromptSubmit hook: inject the bundled agent-fleet SKILL.md when the
# prompt invokes deep-research or ultracode. Exists because the description
# alone barely fires: trigger-eval 2026-08-06 measured 2 of 30 should-trigger
# runs for the shipped description (per-query recall 0.00-0.33), and no
# optimizer rewrite improved the held-out score — so the trigger is mechanical
# string match, not model persuasion. Keep the pattern narrow: the same eval
# measured zero false triggers in 150 negative runs, and widening it is what
# would break that. Records: bench/results/2026-08-06-trigger-eval/ in
# https://github.com/4nrry/agent-plugins.
set -euo pipefail

# Resolve the plugin root from the script's own location rather than
# ${CLAUDE_PLUGIN_ROOT}: works identically when run by the hook runner,
# by hand, or from a copied tree.
PLUGIN_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

prompt=$(jq -r '.prompt // empty' 2>/dev/null) || exit 0
[[ -n "$prompt" ]] || exit 0

printf '%s' "$prompt" | grep -qiE 'ultracode|deep[- ]research' || exit 0

if [[ ! -f "$PLUGIN_ROOT/SKILL.md" ]]; then
  echo "agent-fleet plugin hook: $PLUGIN_ROOT/SKILL.md not found — skill not injected" >&2
  exit 1
fi

printf 'The agent-fleet skill applies to this request (matched: deep-research/ultracode). Follow it when orchestrating. Before dispatching any predefined workflow, read its script and check for model: overrides on the agent() calls — without them every agent inherits the session model, at fan-out scale; this is the rule most often skipped. Skill directory: %s (scripts/ paths below are relative to it).\n\n' "$PLUGIN_ROOT"
cat "$PLUGIN_ROOT/SKILL.md"
