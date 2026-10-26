#!/usr/bin/env bash
# UserPromptSubmit hook: inject the bundled agent-fleet SKILL.md when the prompt
# names a fan-out (ultracode, deep research, dynamic workflow, /dwf, /fleet) or
# asks for research from many sources: a form of "pesquisa" next to a sign of
# several sources (fontes, links, artigos, estudos, compara, changelogs,
# releases, Reddit, comunidade, "o que estão falando", no X, concorrentes,
# agentes, a fundo, de mercado, DOI). String match, not intent, because the
# description alone barely fires: 3 of 30 runs on "pesquisa" prompts
# (2026-10-26) and 2 of 30 in English (2026-08-06). The 2026-10-26 sets, a
# runner for this script and the scores are in
# bench/plugins/agent-fleet/results/2026-10-26-pesquisa-trigger/ in
# https://github.com/4nrry/agent-plugins: on a set written blind after the rule,
# 12 of 15 should-trigger prompts fired and 0 of 15 near-misses did. Keep the
# research arm two-sided: "pesquisa" alone fired on 9 of 13 near-misses
# (code search, survey forms, a search box). Patterns are POSIX ERE, no \b or
# \s, so GNU grep, BSD grep and ugrep agree.
set -euo pipefail

# Resolve the plugin root from the script's own location rather than
# ${CLAUDE_PLUGIN_ROOT}: works identically when run by the hook runner,
# by hand, or from a copied tree.
# The skill lives in skills/agent-fleet/ (the Agent Plugins layout).
SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../skills/agent-fleet" && pwd)"

prompt=$(jq -r '.prompt // empty' 2>/dev/null) || exit 0
[[ -n "$prompt" ]] || exit 0

B='(^|[^[:alnum:]])'
E='([^[:alnum:]]|$)'
WORKFLOW="ultracode|deep[- ]research|dynamic[- ]workflows?|/dwf${E}|workflows?[- ]din(a|â)mic|/fleet${E}"
SOURCES="aprofund|a[[:space:]]+fundo|profund|de[[:space:]]+mercado|compar|${B}vs\\.?${E}|${B}fontes?${E}|${B}links?${E}|papers?${E}"
SOURCES+="|${B}artigos${E}|${B}estudos${E}|changelogs?|releases|reddit|hacker[[:space:]]*news|comunidade"
SOURCES+="|o[[:space:]]+que[[:space:]]+(o[[:space:]]+pessoal|est(a|ã)o|t(a|ã)o)${E}|${B}no[[:space:]]+x${E}"
SOURCES+="|em[[:space:]]+paralelo|agentes|concorrentes|${B}doi${E}|${B}cit(a|e)${E}"

matches() { printf '%s' "$prompt" | grep -qiE -- "$1"; }
if matches "$WORKFLOW"; then
  why="a fan-out or deep research"
elif matches 'pesquis' && matches "$SOURCES"; then
  why="research from many sources"
else
  exit 0
fi

if [[ ! -f "$SKILL_DIR/SKILL.md" ]]; then
  echo "agent-fleet plugin hook: $SKILL_DIR/SKILL.md not found — skill not injected" >&2
  exit 1
fi

printf 'The agent-fleet skill applies to this request (matched: %s). Follow it when orchestrating. Search X only when the question is about posts, announcements, an account or what people say, or the user asks for it. Before dispatching any predefined workflow, read its script and check for model: overrides on the agent() calls — without them every agent inherits the session model, at fan-out scale; this is the rule most often skipped. Skill directory: %s (scripts/ and references/ paths below are relative to it).\n\n' "$why" "$SKILL_DIR"
cat "$SKILL_DIR/SKILL.md"
