#!/usr/bin/env bash
# PreToolUse / Bash — warns before `adb kill-server`.
#
# Why: restarting the adb server drops every `adb reverse` tunnel from every
# session, and the app loses its stack with nothing in its own logs. The symptom
# looks like a bad cable or a disconnected device.
#
# Never blocks: `adb kill-server` is legitimate when the server is truly hung;
# the hook only discourages running it as a reflex on the first error.
set -uo pipefail

input=$(cat) || exit 0
cmd=$(jq -r '.tool_input.command // empty' <<<"$input" 2>/dev/null) || exit 0
[[ -n "$cmd" ]] || exit 0

# Re-check: the `if` in hooks.json already filters, but a harness that ignores it
# would send every Bash command here.
grep -qE '(^|[;&|[:space:]])adb[[:space:]]+kill-server([[:space:]]|$)' <<<"$cmd" || exit 0

jq -n '{
  hookSpecificOutput: {
    hookEventName: "PreToolUse",
    additionalContext: (
      "adb kill-server drops ALL `adb reverse` tunnels on the machine, from every " +
      "session, not just yours. The app loses its stack and the symptom looks like " +
      "a backend outage.\n" +
      "First: `adb devices` shows whether the server responds, and " +
      "`adb reverse --list` shows what you would lose. If only one device went " +
      "missing, `adb reconnect` fixes it without killing the server.\n" +
      "Afterwards, if you proceed: re-apply the tunnels that were up."
    )
  }
}' 2>/dev/null || exit 0
exit 0
