#!/usr/bin/env bash
# Gera UMA imagem com o Grok Build oficial (`grok`) sem tela, pela cota da SuperGrok,
# e confere que o arquivo saiu. Mais rapido que o agy (~40 s): bom para explorar
# variacoes antes de escolher a direcao.
#
#   grok-imagem.sh "descricao da cena" saida.png
set -euo pipefail
[ "$#" -eq 2 ] || { sed -n '2,7p' "$0"; exit 2; }
desc=$1
out=$(realpath -m "$2")
command -v grok >/dev/null || { echo "grok-imagem: grok nao esta no PATH" >&2; exit 1; }
dir=$(dirname "$out")
mkdir -p "$dir"

prompt="Use sua ferramenta nativa de geracao de imagem para gerar UMA imagem: $desc. \
Salve exatamente em $out. Nao escreva codigo para desenhar. No fim responda so com o caminho do arquivo."

grok -p "$prompt" --cwd "$dir" --always-approve --output-format json \
  > "$out.grok.json" 2> "$out.grok.err" || { echo "grok falhou; veja $out.grok.err" >&2; exit 1; }
[ -s "$out" ] || { echo "grok terminou sem gerar $out; resposta em $out.grok.json" >&2; exit 1; }
command -v magick >/dev/null && magick identify -format "%m %wx%h\n" "$out"
rm -f "$out.grok.json" "$out.grok.err"
echo "$out"
