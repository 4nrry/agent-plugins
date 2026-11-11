#!/usr/bin/env bash
# UserPromptSubmit hook: inject the bundled agent-fleet SKILL.md when the prompt
# names a fan-out (ultracode, deep research, dynamic workflow, /dwf, /fleet), asks
# for several subagents at once ("5 subagentes em paralelo", "one subagent per
# folder"; added after a 2026-10-28 headless run where that prompt loaded no
# fleet rules), or
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
#
# The full SKILL.md goes in once per session. A marker named after the
# session id records it; later matches print one line that points back to the
# file. `inject.sh --forget` (SessionStart after a compaction or a clear)
# removes the marker, since the injected text may be gone from the context.
# The marker is used only where the host sets CLAUDE_PLUGIN_DATA, which is
# Claude Code: the bridges for other harnesses run this hook with no
# SessionStart event, so a marker there would never be removed. Without that
# variable, a session id or a writable directory, the hook injects every time,
# as it did before.
set -euo pipefail

# Arguments: `--root DIR`, the plugin folder as hooks.json writes it from
# ${CLAUDE_PLUGIN_ROOT}, and `--forget`. The argument serves a harness that
# fills the placeholder into the command without exporting the variable; with
# no argument the variable itself is used.
ROOT="${CLAUDE_PLUGIN_ROOT:-}"
forget=""
while (( $# )); do
  case "$1" in
    --root) ROOT="${2:-}"; shift ;;
    --forget) forget=1 ;;
  esac
  shift || true
done

command -v jq >/dev/null || { echo "agent-fleet inject hook: jq not found, skill not injected" >&2; exit 0; }
input=$(cat) || exit 0

MARKERS=""
if [[ -n "${CLAUDE_PLUGIN_DATA:-}" ]]; then MARKERS="$CLAUDE_PLUGIN_DATA/injected"; fi
sid=$(jq -r '.session_id // empty' <<<"$input" 2>/dev/null) || sid=""
[[ "$sid" =~ ^[A-Za-z0-9_-]{1,128}$ ]] || sid=""
marker=""
if [[ -n "$MARKERS" && -n "$sid" ]]; then marker="$MARKERS/$sid"; fi

if [[ -n "$forget" ]]; then
  [[ -z "$marker" ]] || rm -f -- "$marker" 2>/dev/null || true
  exit 0
fi

prompt=$(jq -r '.prompt // empty' <<<"$input" 2>/dev/null) || exit 0
[[ -n "$prompt" ]] || exit 0

B='(^|[^[:alnum:]])'
E='([^[:alnum:]]|$)'
WORKFLOW="ultracode|deep[- ]research|dynamic[- ]workflows?|/dwf${E}|workflows?[- ]din(a|â)mic|/fleet${E}"
SOURCES="aprofund|a[[:space:]]+fundo|profund|de[[:space:]]+mercado|compar|${B}vs\\.?${E}|${B}fontes?${E}|${B}links?${E}|${B}papers?${E}"
SOURCES+="|${B}artigos${E}|${B}estudos${E}|changelogs?|releases|reddit|hacker[[:space:]]*news|comunidade"
SOURCES+="|o[[:space:]]+que[[:space:]]+(o[[:space:]]+pessoal|est(a|ã)o|t(a|ã)o)${E}|${B}no[[:space:]]+x${E}"
SOURCES+="|em[[:space:]]+paralelo|agentes|concorrentes|${B}doi${E}|${B}cit(a|e)${E}"
# Several agents at once. "agente" alone is too common (a health agent, an
# agent definition), so it needs a count right before it or a parallel word;
# "each" and "one per" count only next to "subagent". "Team of agents" and
# "one agent per X" were tried and dropped: they fire on support, sales and
# health agents (logs/agent-business-nearmiss-2026-10-28.json).
AGENT="(sub-?)?agent(e|s|es)?"
TOGETHER="paralel|parallel|ao[[:space:]]+mesmo[[:space:]]+tempo|at[[:space:]]+once|simult"
NUM="[0-9]+|dois|duas|tr(e|ê)s|quatro|cinco|seis|sete|oito|dez|v(a|á)ri(o|a)s|alguns|two|three|four|five|six|eight|ten|several|multiple|many"
FANOUT="fan[- ]?out|${B}(${NUM})[[:space:]]+${AGENT}${E}"

# A here-string, not a pipe: with pipefail, grep -q leaving at its first match
# kills the writer (SIGPIPE) and the pipeline reads as "no match". A prompt of
# a few thousand lines with the trigger near the top was missed that way.
matches() { grep -qiE -- "$1" <<<"$prompt"; }
if matches "$WORKFLOW"; then
  why="a fan-out or deep research"
elif matches "$FANOUT" \
  || { matches "${B}${AGENT}${E}" && matches "$TOGETHER"; } \
  || { matches "sub-?agent" && matches "${B}(cada|each)${E}|um[[:space:]]+por|uma[[:space:]]+por|one[[:space:]]+per"; }; then
  why="several agents at once"
elif matches 'pesquis' && matches "$SOURCES"; then
  why="research from many sources"
else
  exit 0
fi

# The plugin folder is ${CLAUDE_PLUGIN_ROOT}, as an argument or as the
# variable: Claude Code sets it for a plugin's hooks, and so do the bridges
# for other harnesses. Run by hand, pass --root. The skill lives in
# skills/agent-fleet/ (the Agent Plugins layout).
if [[ -z "$ROOT" ]]; then
  echo "agent-fleet plugin hook: no plugin folder (--root or CLAUDE_PLUGIN_ROOT) — skill not injected" >&2
  exit 1
fi
SKILL_DIR="${ROOT%/}/skills/agent-fleet"
[[ "$SKILL_DIR" == /* ]] || SKILL_DIR="$PWD/$SKILL_DIR"
if [[ ! -f "$SKILL_DIR/SKILL.md" ]]; then
  echo "agent-fleet plugin hook: $SKILL_DIR/SKILL.md not found — skill not injected" >&2
  exit 1
fi

ROUTING='Before dispatching any predefined workflow, read its script and check for model: overrides on the agent() calls — without them every agent inherits the session model, at fan-out scale; this is the rule most often skipped.'

if [[ -n "$marker" && -e "$marker" ]]; then
  printf 'The agent-fleet skill applies to this request (matched: %s). Its text was injected earlier in this session; if it is no longer in your context, read %s/SKILL.md before orchestrating. %s\n' "$why" "$SKILL_DIR" "$ROUTING"
  exit 0
fi

printf 'The agent-fleet skill applies to this request (matched: %s). Follow it when orchestrating. %s Skill directory: %s (scripts/ and references/ paths below are relative to it).\n\n' "$why" "$ROUTING" "$SKILL_DIR"
cat "$SKILL_DIR/SKILL.md"

if [[ -n "$marker" ]] && mkdir -p "$MARKERS" 2>/dev/null; then
  { : >"$marker"; } 2>/dev/null || true
  # One marker per session would pile up for as long as the data directory lives.
  find "$MARKERS" -maxdepth 1 -type f -mtime +7 -delete 2>/dev/null || true
fi
