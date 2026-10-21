#!/usr/bin/env bash
# Normalize each voice-over sentence to a LUFS target (two loudnorm passes plus a
# correction) and write a JSON with each file's real duration, for captions and ducking.
#
#   vo-normalize.sh [-I -16] [-T -1.5] [-L 11] [-o OUTDIR] [-j DURATIONS.json] IN.wav...
#
# Output: OUTDIR/<name>.wav (48 kHz, same channels) and the JSON [{"id","file","duration","lufs"}].
# Needs ffmpeg, ffprobe and jq.
set -euo pipefail

target=-16
tp=-1.5
lra=11
outdir=vo-norm
json=""
while getopts 'I:T:L:o:j:h' opt; do
  case "$opt" in
    I) target=$OPTARG ;;
    T) tp=$OPTARG ;;
    L) lra=$OPTARG ;;
    o) outdir=$OPTARG ;;
    j) json=$OPTARG ;;
    *) sed -n '2,8p' "$0"; exit 2 ;;
  esac
done
shift $((OPTIND - 1))
[ "$#" -gt 0 ] || { sed -n '2,8p' "$0"; exit 2; }
for t in ffmpeg ffprobe jq; do
  command -v "$t" >/dev/null || { echo "vo-normalize: missing $t" >&2; exit 1; }
done
mkdir -p "$outdir"

# Integrated loudness of a file, measured by loudnorm itself (ebur128 agrees within 0.1 LU).
measure() {
  ffmpeg -hide_banner -nostats -i "$1" -af "loudnorm=I=$target:TP=$tp:LRA=$lra:print_format=json" -f null - 2>&1 \
    | sed -n '/^{/,/^}/p' | jq -r '.input_i'
}

rows=()
for in_file in "$@"; do
  name=$(basename "$in_file")
  id=${name%.*}
  out="$outdir/$id.wav"

  # Pass 1: measure. ffmpeg prints the loudnorm JSON on stderr after other lines;
  # the block runs from the first "{" to the end.
  measured=$(ffmpeg -hide_banner -nostats -i "$in_file" \
    -af "loudnorm=I=$target:TP=$tp:LRA=$lra:print_format=json" -f null - 2>&1 \
    | sed -n '/^{/,/^}/p')
  read -r mi mtp mlra mth < <(jq -r '[.input_i, .input_tp, .input_lra, .input_thresh] | @tsv' <<<"$measured")

  # Pass 2: apply with the measured values (linear=true only when it fits the true-peak limit).
  ffmpeg -hide_banner -loglevel error -y -i "$in_file" \
    -af "loudnorm=I=$target:TP=$tp:LRA=$lra:measured_I=$mi:measured_TP=$mtp:measured_LRA=$mlra:measured_thresh=$mth:linear=true:print_format=summary" \
    -ar 48000 "$out" 2>/dev/null

  # Pass 3: speech has a high crest factor, so the true-peak ceiling leaves loudnorm
  # 1-2 LU under target on short sentences. Re-measure and add the missing gain
  # with a limiter at the same ceiling.
  got=$(measure "$out")
  diff=$(awk -v t="$target" -v g="$got" 'BEGIN { printf "%.2f", t - g }')
  if awk -v d="$diff" 'BEGIN { exit !(d > 0.3 || d < -0.3) }'; then
    lim=$(awk -v tp="$tp" 'BEGIN { printf "%.4f", 10 ^ (tp / 20) }')
    ffmpeg -hide_banner -loglevel error -y -i "$out" \
      -af "volume=${diff}dB,alimiter=limit=$lim:attack=5:release=50:level=false" "$out.tmp.wav" 2>/dev/null
    mv "$out.tmp.wav" "$out"
  fi

  dur=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$out")
  lufs=$(measure "$out")
  printf '%s  %6.2fs  %s LUFS (was %s)\n' "$out" "$dur" "${lufs:-?}" "$mi"
  rows+=("$(jq -cn --arg id "$id" --arg f "$out" --argjson d "$dur" --arg l "${lufs:-null}" \
    '{id: $id, file: $f, duration: ($d * 100 | round / 100), lufs: ($l | tonumber? // null)}')")
done

if [ -n "$json" ]; then
  printf '%s\n' "${rows[@]}" | jq -s . >"$json"
  echo "$json"
fi
