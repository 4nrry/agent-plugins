#!/usr/bin/env bash
# Generate ONE image headless with the official Antigravity CLI (`agy`), using the
# Google AI Pro/Ultra subscription quota, and check that the file was written.
#
#   agy-image.sh "scene description" out.png
#
# Runs the official binary and never touches its login: reusing agy's token in
# another tool violates the Antigravity terms.
set -euo pipefail
[ "$#" -eq 2 ] || { sed -n '2,8p' "$0"; exit 2; }
desc=$1
out=$(realpath -m "$2")
command -v agy >/dev/null || { echo "agy-image: agy is not on PATH" >&2; exit 1; }
dir=$(dirname "$out")
mkdir -p "$dir"

prompt="Generate ONE image with your native image generation tool (generate_image): $desc. \
Save the file exactly at $out. Do not write code to draw the image. \
At the end, reply with only the absolute path of the file."

# --sandbox restricts the agent's terminal; --dangerously-skip-permissions keeps
# headless mode from blocking on an approval prompt.
cd "$dir"
agy -p "$prompt" --output-format json --dangerously-skip-permissions --sandbox --print-timeout 9m \
  > "$out.agy.json" 2> "$out.agy.err" || { echo "agy failed; see $out.agy.err" >&2; exit 1; }

[ -s "$out" ] || { echo "agy finished without writing $out; response in $out.agy.json" >&2; exit 1; }
if command -v magick >/dev/null; then
  magick identify -format "%m %wx%h\n" "$out"
fi
rm -f "$out.agy.json" "$out.agy.err"
echo "$out"
