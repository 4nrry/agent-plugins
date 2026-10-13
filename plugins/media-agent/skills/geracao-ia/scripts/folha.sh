#!/usr/bin/env bash
# Monta uma folha de contato para comparar variacoes lado a lado: imagens entram
# inteiras, videos entram como 4 quadros espacados. Saida em JPG para revisar.
#
#   folha.sh saida.jpg arquivo1.png arquivo2.mp4 ...
set -euo pipefail
[ "$#" -ge 2 ] || { sed -n '2,6p' "$0"; exit 2; }
out=$1
shift
for t in magick ffmpeg ffprobe; do command -v "$t" >/dev/null || { echo "folha: falta $t" >&2; exit 1; }; done
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

i=0
for f in "$@"; do
  i=$((i + 1))
  name=$(basename "$f")
  case "${f,,}" in
    *.mp4|*.mov|*.webm|*.mkv)
      dur=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$f")
      step=$(awk -v d="$dur" 'BEGIN { printf "%.3f", d / 4 }')
      ffmpeg -v error -y -i "$f" -vf "fps=1/$step,scale=480:-2,tile=4x1" -frames:v 1 "$tmp/$i.png"
      ;;
    *)
      magick "$f" -resize 960x540 "$tmp/$i.png"
      ;;
  esac
  magick "$tmp/$i.png" -background '#222' -fill white -pointsize 22 label:"$name" -gravity center -append "$tmp/$i.png"
done
magick "$tmp"/*.png -background '#222' -gravity center -append -quality 85 "$out"
echo "$out"
