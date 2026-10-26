#!/usr/bin/env bash
# Speak ONE sentence with the TTS Hermes is configured for (here xAI, voice liora,
# pt-BR, on the SuperGrok subscription) and copy the audio to OUT. Runs the
# official hermes CLI and never touches its login.
#
#   hermes-tts.sh "text to speak" out.mp3
set -euo pipefail
[ "$#" -eq 2 ] || { sed -n '2,6p' "$0"; exit 2; }
text=$1
out=$(realpath -m "$2")
command -v hermes >/dev/null || { echo "hermes not found on PATH" >&2; exit 1; }
command -v jq >/dev/null || { echo "jq not found on PATH" >&2; exit 1; }

log=$(mktemp)
trap 'rm -f "$log"' EXIT
hermes chat -q "Use the text-to-speech tool once to speak exactly this text, verbatim, and nothing else: $text" \
  -t tts -Q --format stream-json --ignore-rules >"$log" 2>/dev/null || true

# The tool's result is a JSON string in .output; take the last successful file.
src=$(jq -r 'select(.type == "tool_result" and .name == "text_to_speech") | .output
             | (fromjson? // {}) | select(.success == true) | .file_path' "$log" | tail -n 1)
if [ -z "$src" ] || [ ! -s "$src" ]; then
  echo "hermes produced no audio; last events:" >&2
  tail -c 800 "$log" >&2
  exit 1
fi
mkdir -p "$(dirname "$out")"
cp "$src" "$out"
echo "$out"
