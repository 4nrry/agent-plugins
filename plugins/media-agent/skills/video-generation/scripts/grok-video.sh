#!/usr/bin/env bash
# Generate a short clip headless with the official Grok Build CLI (`grok`), using
# the SuperGrok quota, and check that the MP4 was written. With --image, animates
# an existing image as the first frame.
#
#   grok-video.sh "motion description" out.mp4 [--image frame.png] [--res 720p]
#
# Without --res the API generates 480p (its default). --res is passed to the agent
# in the prompt.
#
# Under ZDR privacy, video is only produced if ~/.grok/managed_config.toml has a
# [tools.zdr_video_output_s3] section pointing to your own bucket (see references/tools.md).
set -euo pipefail
[ "$#" -ge 2 ] || { sed -n '2,12p' "$0"; exit 2; }
desc=$1
out=$(realpath -m "$2")
shift 2
image=""
res=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --image) image=$(realpath "$2"); shift 2 ;;
    --res) res=$2; shift 2 ;;
    *) echo "grok-video: unknown option $1" >&2; exit 2 ;;
  esac
done
quality=""
[ -n "$res" ] && quality=" Generate at $res resolution, not the default 480p."
command -v grok >/dev/null || { echo "grok-video: grok is not on PATH" >&2; exit 1; }
dir=$(dirname "$out")
mkdir -p "$dir"

if [ -n "$image" ]; then
  prompt="Animate the existing image $image with your native video tool, using THAT image as \
the first frame (do not generate a new frame). Motion: $desc.$quality Save as $out. \
Do not write code to create the video. At the end, reply with only the file path."
else
  prompt="Use your native video generation tool to generate ONE short video: $desc.$quality \
Save as $out. Do not write code to create the video. At the end, reply with only the file path."
fi

grok -p "$prompt" --cwd "$dir" --always-approve --output-format json \
  > "$out.grok.json" 2> "$out.grok.err" || { echo "grok failed; see $out.grok.err" >&2; exit 1; }

if [ ! -s "$out" ]; then
  echo "grok finished without writing $out. Response:" >&2
  jq -r '.text // .' "$out.grok.json" >&2 2>/dev/null || cat "$out.grok.json" >&2
  exit 1
fi
command -v ffprobe >/dev/null && ffprobe -v error -select_streams v:0 \
  -show_entries stream=width,height,r_frame_rate:format=duration -of compact "$out"
rm -f "$out.grok.json" "$out.grok.err"
echo "$out"
