#!/usr/bin/env bash
# Generate ONE image headless with the official Grok Build CLI (`grok`), using the
# SuperGrok quota, and check that the file was written. Faster than agy: good for
# exploring variations before picking a direction.
#
#   grok-image.sh "scene description" out.png
set -euo pipefail
[ "$#" -eq 2 ] || { sed -n '2,6p' "$0"; exit 2; }
desc=$1
out=$(realpath -m "$2")
command -v grok >/dev/null || { echo "grok-image: grok is not on PATH" >&2; exit 1; }
dir=$(dirname "$out")
mkdir -p "$dir"

prompt="Use your native image generation tool to generate ONE image: $desc. \
Save it exactly at $out. Do not write code to draw it. At the end, reply with only the file path."

grok -p "$prompt" --cwd "$dir" --always-approve --output-format json \
  > "$out.grok.json" 2> "$out.grok.err" || { echo "grok failed; see $out.grok.err" >&2; exit 1; }
[ -s "$out" ] || { echo "grok finished without writing $out; response in $out.grok.json" >&2; exit 1; }
command -v magick >/dev/null && magick identify -format "%m %wx%h\n" "$out"
rm -f "$out.grok.json" "$out.grok.err"
echo "$out"
