#!/usr/bin/env bash
# PreToolUse / Bash — warns when a `pkill`/`pgrep` matches its own command line.
#
# Why: `pkill -f foo` inside a command that contains `foo` kills its own shell,
# and the bracket trick does not help: `pgrep -f '[f]oo'` still matches if the
# word appears anywhere else on the line, even inside an echo. No linter catches
# this.
set -uo pipefail

input=$(cat) || exit 0
cmd=$(jq -r '.tool_input.command // empty' <<<"$input" 2>/dev/null) || exit 0
[[ -n "$cmd" ]] || exit 0

# Only the form that matches the full command line matters: -f (or --full).
# The flag rarely sits right after the name (`pkill -9 -f node` is the common,
# deadly form), so allow other flags in between.
grep -qE '(^|[;&|[:space:]])(pkill|pgrep)([[:space:]]+-[^[:space:]]+)*[[:space:]]+(-[a-zA-Z]*f([[:space:]]|$)|--full)' <<<"$cmd" || exit 0

jq -n '{
  hookSpecificOutput: {
    hookEventName: "PreToolUse",
    additionalContext: (
      "`pkill -f` / `pgrep -f` match against the ENTIRE command line, including " +
      "this very command. If the pattern appears here — even inside an echo, a " +
      "comment or a path — you match yourself: pkill kills the shell, pgrep " +
      "reports a process that does not exist.\n" +
      "The bracket trick does NOT fix this. Alternatives that do not self-match: " +
      "`pkill -x <exact-name>`, `pgrep -x`, or read /proc cmdlines and filter " +
      "by a PID obtained beforehand.\n" +
      "And the companion rule: do not kill processes you did not start — " +
      "emulators, Metro, containers and dev servers may belong to another " +
      "session or to the user."
    )
  }
}' 2>/dev/null || exit 0
exit 0
