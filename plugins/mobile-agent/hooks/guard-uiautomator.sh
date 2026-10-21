#!/usr/bin/env bash
# PreToolUse / Bash — warns when `uiautomator dump` writes to a file.
#
# Why: `uiautomator dump /sdcard/ui.xml` sometimes fails silently. The previous
# file stays, so you read the XML from the PAST run and conclude the screen
# froze when it already changed.
#
# `adb exec-out uiautomator dump /dev/tty` returns it on stdout, with no
# intermediate file and no stale state.
set -uo pipefail

input=$(cat) || exit 0
cmd=$(jq -r '.tool_input.command // empty' <<<"$input" 2>/dev/null) || exit 0
[[ -n "$cmd" ]] || exit 0

grep -q 'uiautomator[[:space:]]\+dump' <<<"$cmd" || exit 0
# Already in the correct form: nothing to say.
grep -q '/dev/tty' <<<"$cmd" && exit 0

jq -n '{
  hookSpecificOutput: {
    hookEventName: "PreToolUse",
    additionalContext: (
      "`uiautomator dump` to a FILE sometimes fails silently and the old file " +
      "stays — you read the previous run'\''s tree and conclude the screen froze. " +
      "Prefer `adb exec-out uiautomator dump /dev/tty`, which comes back on " +
      "stdout with no stale state.\n" +
      "Also know the limit: GL surfaces (MapLibre, maps, video, WebView) do NOT " +
      "appear in the accessibility tree, so an empty dump there does not mean " +
      "the app froze. For those screens go visual — `android screen capture " +
      "--annotate` plus `android screen resolve --screenshot <png> --string \"tap #N\"`. " +
      "Note `--screenshot`: Google'\''s own skill docs say `--screen`, " +
      "which the binary rejects."
    )
  }
}' 2>/dev/null || exit 0
exit 0
