#!/usr/bin/env bash
# PreToolUse / Bash — warns when `scrcpy` runs without `ADB` set while more than
# one adb is within reach.
#
# Why: scrcpy uses the adb from the ADB variable, else the first on PATH (man
# page, ENVIRONMENT). If that is not the adb Metro, the emulator and
# `adb reverse` already use, two server versions fight and the second kills the
# first, taking the tunnels with it. The symptom shows up in the APP ("could not
# load"), not in the mirror.
#
# Speaks only when there really are two candidates: ADB unset, the SDK adb
# exists, and either another adb is on PATH or scrcpy ships one beside itself.
set -uo pipefail

input=$(cat) || exit 0
cmd=$(jq -r '.tool_input.command // empty' <<<"$input" 2>/dev/null) || exit 0
[[ -n "$cmd" ]] || exit 0

grep -qE '(^|[;&|[:space:]])scrcpy([[:space:]]|$)' <<<"$cmd" || exit 0
# ADB pinned on the line itself, or inherited from the environment: nothing to say.
grep -qE '(^|[[:space:]])ADB=' <<<"$cmd" && exit 0
[[ -n "${ADB:-}" ]] && exit 0

sdk="${ANDROID_HOME:-$HOME/Android/Sdk}/platform-tools/adb"
[[ -x "$sdk" ]] || exit 0

other=""
exe=$(command -v scrcpy 2>/dev/null || true)
if [[ -n "$exe" ]]; then
  real=$(readlink -f "$exe" 2>/dev/null || printf '%s' "$exe")
  [[ -x "$(dirname "$real")/adb" ]] && other="$(dirname "$real")/adb"
fi
if [[ -z "$other" ]]; then
  first=$(command -v adb 2>/dev/null || true)
  if [[ -n "$first" ]]; then
    [[ "$(readlink -f "$first")" != "$(readlink -f "$sdk")" ]] && other="$first"
  fi
fi
[[ -n "$other" ]] || exit 0

jq -n --arg sdk "$sdk" --arg other "$other" '{
  hookSpecificOutput: {
    hookEventName: "PreToolUse",
    additionalContext: (
      "scrcpy without ADB set: it will use `" + $other + "`, while the rest of " +
      "the session (Metro, emulator, adb reverse) uses `" + $sdk + "`. Two adb " +
      "versions restart each other'\''s server and drop the tunnels; the symptom " +
      "shows up in the app, not in the mirror.\n" +
      "Prefix: ADB=" + $sdk + " scrcpy ... (or pin it in a wrapper; skill " +
      "android-mirror)."
    )
  }
}' 2>/dev/null || exit 0
exit 0
