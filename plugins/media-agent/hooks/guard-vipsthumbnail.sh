#!/usr/bin/env bash
# PreToolUse / Bash: warn when `vipsthumbnail -o NAME` will write to the wrong place.
#
# Why: vipsthumbnail's `-o` is a name FORMAT, not an output path. Without a slash
# the file lands in the INPUT file's directory, not the cwd. For example,
# `vipsthumbnail repo/public/photo.jpg -s 480 -o photo-480.png` run from a scratch
# dir leaves an untracked `photo-480.png` inside the repo and the scratch dir empty.
set -uo pipefail

input=$(cat) || exit 0
cmd=$(jq -r '.tool_input.command // empty' <<<"$input" 2>/dev/null) || exit 0
[[ -n "$cmd" ]] || exit 0

# Only `-o`/`--output` values without a slash matter; a value with a slash is an
# explicit path and does what it looks like.
# The value may be quoted, and the match stops at ; & | so a later command's
# -o does not count.
grep -qE '(^|[;&|[:space:]])vipsthumbnail[[:space:]][^;&|]*(-o|--output)[[:space:]=]+["'"'"']?[^/[:space:]"'"'"']+["'"'"']?([[:space:]]|$)' <<<"$cmd" || exit 0

jq -n '{
  hookSpecificOutput: {
    hookEventName: "PreToolUse",
    additionalContext: (
      "`vipsthumbnail -o NAME` without a slash writes NAME to the INPUT " +
      "file'"'"'s directory, not the current directory. If the input is in a " +
      "repository, the thumbnail lands there, untracked, and the cwd stays " +
      "empty. Pass a path with a directory in -o (for example " +
      "`-o /tmp/x/%s-480.png` or `-o ./out.png`), or use " +
      "`magick IN -resize 480x480 OUT`."
    )
  }
}'
