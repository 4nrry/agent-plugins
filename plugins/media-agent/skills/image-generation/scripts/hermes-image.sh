#!/usr/bin/env bash
# Generate ONE image with the image model Hermes is configured for (here xAI's
# grok-imagine-image-2.0, on the Grok subscription) and download it to OUT.
# Runs the official hermes CLI and never touches its login.
#
#   hermes-image.sh "scene description" out.jpg [landscape|square|portrait]
#
# xAI returns a JPEG (1280x720 at its default "1k"; set image_gen.xai.resolution
# to "2k" in ~/.hermes/config.yaml for more). With image_gen.xai.storage.public_url
# on, the file also sits at a public x.ai URL until it expires.
set -euo pipefail
[ "$#" -ge 2 ] && [ "$#" -le 3 ] || { sed -n '2,10p' "$0"; exit 2; }
desc=$1
out=$(realpath -m "$2")
aspect=${3:-landscape}
command -v hermes >/dev/null || { echo "hermes not found on PATH" >&2; exit 1; }
command -v jq >/dev/null || { echo "jq not found on PATH" >&2; exit 1; }

log=$(mktemp)
trap 'rm -f "$log"' EXIT
hermes chat -q "Use the image generation tool once, aspect ratio $aspect, with exactly this prompt: $desc" \
  -t image_gen -Q --format stream-json --ignore-rules >"$log" 2>/dev/null || true

src=$(jq -r 'select(.type == "tool_result" and .name == "image_generate") | .output
             | (fromjson? // {}) | select(.success == true) | .image' "$log" | tail -n 1)
[ -n "$src" ] || { echo "hermes produced no image; last events:" >&2; tail -c 800 "$log" >&2; exit 1; }
mkdir -p "$(dirname "$out")"
case $src in
  http*) curl -fsS -o "$out" "$src" ;;
  *)     cp "$src" "$out" ;;
esac
[ -s "$out" ] || { echo "download failed: $src" >&2; exit 1; }
echo "$out"
