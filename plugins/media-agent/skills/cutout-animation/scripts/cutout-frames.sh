#!/usr/bin/env bash
# Extract frames from a clip and remove the background from each one, using the
# image-retouching skill's headless ComfyUI (BiRefNet). A second run with the
# same clip and options does nothing; a changed clip or option starts the
# directory over. Starts the ComfyUI server when none is running and stops it
# at the end; a server that was already up is left alone.
#
#   cutout-frames.sh clip.mp4 outdir [--fps 10] [--ss 1.45] [--t 3.6]
#
# Writes outdir/frames/f0001.png ... and outdir/cut/f0001.png ... (RGBA).
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
for tool in ffmpeg curl; do
  command -v "$tool" >/dev/null || { echo "cutout-frames: $tool is not on PATH" >&2; exit 1; }
done
# A server named by COMFY_SERVER is someone else's: use it, never start one for it.
local_server="http://127.0.0.1:${COMFY_PORT:-8188}"
server="${COMFY_SERVER:-$local_server}"
up() { curl -sf -o /dev/null --max-time 2 "$server/system_stats"; }

mkdir -p "$out/frames" "$out/cut"
shopt -s nullglob
# What the frames on disk were made from. A different clip, rate or trim makes
# every old frame and cut-out wrong, so the directory starts over.
made="$(stat -c '%n %s %Y' "$clip") fps=$fps ${trim[*]:-}"
if [ "$(cat "$out/.cutout-frames" 2>/dev/null)" != "$made" ]; then
  rm -f -- "$out/frames"/f*.png "$out/cut"/f*.png "$out/.cutout-frames"
  # -ss after -i is exact; before -i it seeks on keyframes and can shift the cut.
  ffmpeg -v error -y -i "$clip" "${trim[@]}" -vf "fps=$fps" "$out/frames/f%04d.png"
  printf '%s\n' "$made" > "$out/.cutout-frames"
fi
frames=("$out/frames"/f*.png)
[ "${#frames[@]}" -gt 0 ] || { rm -f -- "$out/.cutout-frames"; echo "cutout-frames: ffmpeg wrote no frames (is --ss past the end of the clip?)" >&2; exit 1; }

todo=()
for f in "${frames[@]}"; do
  [ -s "$out/cut/$(basename "$f")" ] || todo+=("$f")
done

started=""
stop_server() { [ -z "$started" ] || kill "$started" 2>/dev/null || true; }
trap stop_server EXIT
if [ "${#todo[@]}" -gt 0 ] && ! up; then
  [ "$server" = "$local_server" ] || { echo "cutout-frames: no ComfyUI answering at $server (COMFY_SERVER)" >&2; exit 1; }
  "$retouch/comfy-serve.sh" >"$out/comfy-serve.log" 2>&1 &
  started=$!
  for _ in $(seq 1 90); do
    up && break
    kill -0 "$started" 2>/dev/null || { echo "cutout-frames: ComfyUI exited; see $out/comfy-serve.log" >&2; exit 1; }
    sleep 2
  done
  up || { echo "cutout-frames: ComfyUI did not answer at $server in 180 s; see $out/comfy-serve.log" >&2; exit 1; }
fi

for f in "${todo[@]}"; do
  python3 "$retouch/comfy-run.py" background "$f" -o "$out/cut/$(basename "$f")" --server "$server" >/dev/null
done
echo "${#frames[@]} frames -> $out/cut (${#todo[@]} cut out now)"
