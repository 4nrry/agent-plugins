#!/usr/bin/env bash
# Gera um clipe curto com o Grok Build oficial (`grok`) sem tela, usando a cota da
# SuperGrok, e confere que o MP4 saiu. Com --image, anima uma imagem existente como
# quadro inicial.
#
#   grok-video.sh "descricao do movimento" saida.mp4 [--image quadro.png] [--res 720p]
#
# Sem --res a API gera em 480p (o padrao dela). --res vai no pedido ao agente.
#
# Sob privacidade ZDR, o video so sai se ~/.grok/managed_config.toml tiver a secao
# [tools.zdr_video_output_s3] apontando para um bucket seu (ver SKILL.md).
set -euo pipefail
[ "$#" -ge 2 ] || { sed -n '2,10p' "$0"; exit 2; }
desc=$1
out=$(realpath -m "$2")
shift 2
image=""
res=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --image) image=$(realpath "$2"); shift 2 ;;
    --res) res=$2; shift 2 ;;
    *) echo "grok-video: opcao desconhecida $1" >&2; exit 2 ;;
  esac
done
quality=""
[ -n "$res" ] && quality=" Gere em resolucao $res, nao no padrao de 480p."
command -v grok >/dev/null || { echo "grok-video: grok nao esta no PATH" >&2; exit 1; }
dir=$(dirname "$out")
mkdir -p "$dir"

if [ -n "$image" ]; then
  prompt="Anime a imagem existente $image com sua ferramenta nativa de video, usando ESSA imagem como \
quadro inicial (nao gere um quadro novo). Movimento: $desc.$quality Salve como $out. \
Nao escreva codigo para criar o video. No fim responda so com o caminho do arquivo."
else
  prompt="Use sua ferramenta nativa de geracao de video para gerar UM video curto: $desc.$quality \
Salve como $out. Nao escreva codigo para criar o video. No fim responda so com o caminho do arquivo."
fi

grok -p "$prompt" --cwd "$dir" --always-approve --output-format json \
  > "$out.grok.json" 2> "$out.grok.err" || { echo "grok falhou; veja $out.grok.err" >&2; exit 1; }

if [ ! -s "$out" ]; then
  echo "grok terminou sem gerar $out. Resposta:" >&2
  jq -r '.text // .' "$out.grok.json" >&2 2>/dev/null || cat "$out.grok.json" >&2
  exit 1
fi
command -v ffprobe >/dev/null && ffprobe -v error -select_streams v:0 \
  -show_entries stream=width,height,r_frame_rate:format=duration -of compact "$out"
rm -f "$out.grok.json" "$out.grok.err"
echo "$out"
