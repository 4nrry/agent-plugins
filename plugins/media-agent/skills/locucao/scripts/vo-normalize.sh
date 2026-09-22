#!/usr/bin/env bash
# Normaliza cada frase de locucao a um alvo LUFS (duas passadas de loudnorm) e
# escreve um JSON com a duracao real de cada arquivo, para a legenda e o ducking.
#
#   vo-normalize.sh [-I -16] [-T -1.5] [-L 11] [-o OUTDIR] [-j DURATIONS.json] IN.wav...
#
# Saida: OUTDIR/<nome>.wav (48 kHz, mesmo canal) e o JSON [{"id","file","duration","lufs"}].
# Precisa de ffmpeg, ffprobe e jq.
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
    *) sed -n '2,9p' "$0"; exit 2 ;;
  esac
done
shift $((OPTIND - 1))
[ "$#" -gt 0 ] || { sed -n '2,9p' "$0"; exit 2; }
for t in ffmpeg ffprobe jq; do
  command -v "$t" >/dev/null || { echo "vo-normalize: falta $t" >&2; exit 1; }
done
mkdir -p "$outdir"

# Loudness integrada de um arquivo, pelo proprio loudnorm (ebur128 concorda em 0,1 LU).
measure() {
  ffmpeg -hide_banner -nostats -i "$1" -af "loudnorm=I=$target:TP=$tp:LRA=$lra:print_format=json" -f null - 2>&1 \
    | sed -n '/^{/,/^}/p' | jq -r '.input_i'
}

rows=()
for in_file in "$@"; do
  name=$(basename "$in_file")
  id=${name%.*}
  out="$outdir/$id.wav"

  # Passada 1: medir. O ffmpeg imprime o JSON do loudnorm no stderr, depois de
  # outras linhas; o bloco vai da primeira "{" ate o fim.
  measured=$(ffmpeg -hide_banner -nostats -i "$in_file" \
    -af "loudnorm=I=$target:TP=$tp:LRA=$lra:print_format=json" -f null - 2>&1 \
    | sed -n '/^{/,/^}/p')
  read -r mi mtp mlra mth < <(jq -r '[.input_i, .input_tp, .input_lra, .input_thresh] | @tsv' <<<"$measured")

  # Passada 2: aplicar com os valores medidos (linear=true so quando cabe no TP).
  ffmpeg -hide_banner -loglevel error -y -i "$in_file" \
    -af "loudnorm=I=$target:TP=$tp:LRA=$lra:measured_I=$mi:measured_TP=$mtp:measured_LRA=$mlra:measured_thresh=$mth:linear=true:print_format=summary" \
    -ar 48000 "$out" 2>/dev/null

  # Passada 3: voz tem crest factor alto, e o teto de true peak faz o loudnorm
  # entregar 1 a 2 LU abaixo do alvo em frase curta. Mede de novo e corrige o
  # que faltou com ganho fixo mais limiter no mesmo teto.
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
  printf '%s  %6.2fs  %s LUFS (era %s)\n' "$out" "$dur" "${lufs:-?}" "$mi"
  rows+=("$(jq -cn --arg id "$id" --arg f "$out" --argjson d "$dur" --arg l "${lufs:-null}" \
    '{id: $id, file: $f, duration: ($d * 100 | round / 100), lufs: ($l | tonumber? // null)}')")
done

if [ -n "$json" ]; then
  printf '%s\n' "${rows[@]}" | jq -s . >"$json"
  echo "$json"
fi
