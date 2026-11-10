#!/usr/bin/env bash
# Extract frames from a clip and remove the background from each one, using the
# image-retouching skill's headless ComfyUI (BiRefNet). Resumable: a frame whose
# cut-out already exists is skipped. Starts the ComfyUI server when none is
# running and stops it at the end; a server that was already up is left alone.
#
#   cutout-frames.sh clip.mp4 outdir [--fps 10] [--ss 1.45] [--t 3.6]
#
# Writes outdir/frames/f001.png ... and outdir/cut/f001.png ... (RGBA).
# Needs ffmpeg, curl and COMFY_HOME (see the image-retouching skill).
set -euo pipefail
[ "$#" -ge 2 ] || { sed -n '2,11p' "$0"; exit 2; }
clip=$(realpath "$1")
out=$(realpath -m "$2")
shift 2
fps=10
trim=()
while [ "$#" -gt 0 ]; do
  case "$1" in
    --fps) fps=$2; shift 2 ;;
    --ss) trim+=(-ss "$2"); shift 2 ;;
    --t) trim+=(-t "$2"); shift 2 ;;
    *) echo "cutout-frames: unknown option $1" >&2; exit 2 ;;
  esac
done
here=$(cd "$(dirname "$0")" && pwd)
retouch="$here/../../image-retouching/scripts"
[ -f "$retouch/comfy-run.py" ] || { echo "cutout-frames: $retouch/comfy-run.py not found (the image-retouching skill ships it)" >&2; exit 1; }
[ -n "${COMFY_HOME:-}" ] || { echo "cutout-frames: set COMFY_HOME (directory with ComfyUI/ and .venv/)" >&2; exit 2; }
command -v ffmpeg >/dev/null || { echo "cutout-frames: ffmpeg is not on PATH" >&2; exit 1; }
server="${COMFY_SERVER:-http://127.0.0.1:${COMFY_PORT:-8188}}"

mkdir -p "$out/frames" "$out/cut"
# -ss before -i seeks on keyframes and can shift the cut; after -i it is exact.
ffmpeg -v error -y -i "$clip" "${trim[@]}" -vf "fps=$fps" "$out/frames/f%03d.png"

todo=0
for f in "$out/frames"/f*.png; do
  [ -s "$out/cut/$(basename "$f")" ] || todo=$((todo + 1))
done

started=""
stop_server() { [ -z "$started" ] || kill "$started" 2>/dev/null || true; }
trap stop_server EXIT
if [ "$todo" -gt 0 ] && ! curl -s -o /dev/null --max-time 2 "$server/system_stats"; then
  "$retouch/comfy-serve.sh" >"$out/comfy-serve.log" 2>&1 &
  started=$!
  for _ in $(seq 1 90); do
    curl -s -o /dev/null --max-time 2 "$server/system_stats" && break
    kill -0 "$started" 2>/dev/null || { echo "cutout-frames: ComfyUI exited; see $out/comfy-serve.log" >&2; exit 1; }
    sleep 2
  done
fi

n=0
for f in "$out/frames"/f*.png; do
  o="$out/cut/$(basename "$f")"
  [ -s "$o" ] || python3 "$retouch/comfy-run.py" background "$f" -o "$o" --server "$server" >/dev/null
  n=$((n + 1))
done
echo "$n frames -> $out/cut"
