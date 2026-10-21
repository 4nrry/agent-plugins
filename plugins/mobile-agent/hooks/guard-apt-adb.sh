#!/usr/bin/env bash
# PreToolUse / Bash — warns before `apt install scrcpy` (or `adb`): the Ubuntu
# package installs a SECOND adb in /usr/bin, ahead of the SDK adb.
#
# Why: Ubuntu's `scrcpy` depends on its `adb` package, and React Native docs say
# to APPEND platform-tools to PATH, so /usr/bin wins. Two adb versions restart
# the server on every call ("adb server version doesn't match this client;
# killing..."), dropping all `adb reverse` tunnels and the wireless connection.
#
# Never blocks: installing is the user's call. Warns only when an SDK adb exists
# to be shadowed; without an SDK the apt adb is the only one.
set -uo pipefail

input=$(cat) || exit 0
cmd=$(jq -r '.tool_input.command // empty' <<<"$input" 2>/dev/null) || exit 0
[[ -n "$cmd" ]] || exit 0

grep -qE '(^|[;&|[:space:]])(sudo[[:space:]]+)?(apt|apt-get)[[:space:]]+install([[:space:]]|$)' <<<"$cmd" || exit 0
grep -qE '(^|[[:space:]])(scrcpy|adb|android-tools-adb)([[:space:]]|$)' <<<"$cmd" || exit 0

sdk="${ANDROID_HOME:-$HOME/Android/Sdk}/platform-tools/adb"
[[ -x "$sdk" ]] || exit 0

jq -n --arg sdk "$sdk" '{
  hookSpecificOutput: {
    hookEventName: "PreToolUse",
    additionalContext: (
      "The apt `scrcpy` package depends on the `adb` package, which lands in " +
      "/usr/bin — BEFORE the SDK adb (" + $sdk + ") on the PATH that the React " +
      "Native docs tell you to set up. Two adb versions restart the server on " +
      "every call and drop all `adb reverse` tunnels and the wireless connection.\n" +
      "Alternative with no second adb: the official scrcpy release tarball, with " +
      "a wrapper that exports ADB=" + $sdk + " (skill android-mirror).\n" +
      "If you go ahead with apt: run `which -a adb` afterwards and leave ONE in front."
    )
  }
}' 2>/dev/null || exit 0
exit 0
