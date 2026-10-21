#!/usr/bin/env bash
# PreToolUse / Bash — warns that `expo run:<platform>` does not prebuild when the
# native directory already exists.
#
# Why: the check is literal in @expo/cli — if the platform directory exists, it
# returns without prebuilding, silently. Changes to app.json, a config plugin or
# an icon are ignored and the build says BUILD SUCCESSFUL in seconds, so you
# conclude the change had no effect and debug the wrong place.
#
# Fires only when the native directory REALLY exists: without it the prebuild
# runs by itself and there is nothing to warn about.
set -uo pipefail

input=$(cat) || exit 0
cmd=$(jq -r '.tool_input.command // empty' <<<"$input" 2>/dev/null) || exit 0
[[ -n "$cmd" ]] || exit 0

grep -qE 'expo[[:space:]]+run:(android|ios)' <<<"$cmd" || exit 0
# An explicit prebuild on the same line: nothing to say.
grep -q 'prebuild' <<<"$cmd" && exit 0

cwd=$(jq -r '.cwd // empty' <<<"$input" 2>/dev/null) || cwd=""
plat="android"
grep -q 'run:ios' <<<"$cmd" && plat="ios"

# The payload `cwd` is the session's, and in a monorepo the command changes
# directory first (`cd apps/mobile && npx expo run:android`). Without following
# that `cd`, the check would look for `android/` at the root and stay silent.
sub=$(sed -n 's/^[[:space:]]*cd[[:space:]]\+\([^;&|]*\).*/\1/p' <<<"$cmd" | head -1)
sub=${sub%"${sub##*[![:space:]]}"}
sub=${sub#\'}; sub=${sub%\'}
sub=${sub#\"}; sub=${sub%\"}
case "$sub" in
  "")  base="$cwd" ;;
  /*)  base="$sub" ;;
  *)   base="$cwd/$sub" ;;
esac
[[ -n "$base" && -d "$base/$plat" ]] || exit 0

# Second warning, Android only: Gradle must find the SDK, and a NON-interactive
# shell often returns early from `~/.bashrc`, so ANDROID_HOME arrives empty and
# the build fails with "SDK location not found" minutes in. An
# `android/local.properties` with `sdk.dir` covers it; without it and without
# the variable, warn.
sdk_note=""
if [[ "$plat" == "android" && -z "${ANDROID_HOME:-}" ]]; then
  if ! grep -qs '^sdk\.dir=' "$base/android/local.properties"; then
    printf -v sdk_note '%s' \
      $'\n\nAlso, ANDROID_HOME is EMPTY in this environment (a non-interactive shell does not read all of ~/.bashrc) and there is no sdk.dir in android/local.properties: Gradle ' \
      $'will stop at \'SDK location not found\'. Export it first, on the same line:\n' \
      $'  export ANDROID_HOME=$HOME/Android/Sdk JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64'
  fi
fi

jq -n --arg p "$plat" --arg sdk "$sdk_note" '{
  hookSpecificOutput: {
    hookEventName: "PreToolUse",
    additionalContext: (
      "The `" + $p + "/` directory already exists in this project, and in that " +
      "case `expo run:" + $p + "` does NOT run the prebuild — the check is literal " +
      "in @expo/cli and emits no warning. Changes to app.json, a config plugin or " +
      "an icon will be ignored silently, and the build will say BUILD SUCCESSFUL " +
      "in seconds.\n" +
      "If you changed any of those, run first:\n" +
      "  npx expo prebuild --platform " + $p + " --clean\n" +
      "If you only changed JS/TS, go ahead: Fast Refresh covers it and there is " +
      "nothing to regenerate." + $sdk
    )
  }
}' 2>/dev/null || exit 0
exit 0
