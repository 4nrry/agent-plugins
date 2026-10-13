#!/usr/bin/env bash
# Gera UMA imagem com o Antigravity CLI oficial (`agy`) sem tela, usando a cota da
# assinatura Google AI Pro/Ultra, e confere que o arquivo saiu.
#
#   agy-imagem.sh "descricao da cena" saida.png
#
# Roda o binario oficial, sem tocar no login dele: extrair ou reaproveitar o token
# do agy em outra ferramenta viola os termos do Antigravity.
set -euo pipefail
[ "$#" -eq 2 ] || { sed -n '2,8p' "$0"; exit 2; }
desc=$1
out=$(realpath -m "$2")
command -v agy >/dev/null || { echo "agy-imagem: agy nao esta no PATH" >&2; exit 1; }
dir=$(dirname "$out")
mkdir -p "$dir"

prompt="Gere UMA imagem com sua ferramenta nativa de geracao de imagem (generate_image): $desc. \
Salve o arquivo exatamente em $out. Nao escreva codigo para desenhar a imagem. \
No fim responda so com o caminho absoluto do arquivo."

# --sandbox restringe o terminal do agente; --dangerously-skip-permissions evita
# que o modo sem tela trave esperando aprovacao.
cd "$dir"
agy -p "$prompt" --output-format json --dangerously-skip-permissions --sandbox --print-timeout 9m \
  > "$out.agy.json" 2> "$out.agy.err" || { echo "agy falhou; veja $out.agy.err" >&2; exit 1; }

[ -s "$out" ] || { echo "agy terminou sem gerar $out; resposta em $out.agy.json" >&2; exit 1; }
if command -v magick >/dev/null; then
  magick identify -format "%m %wx%h\n" "$out"
fi
rm -f "$out.agy.json" "$out.agy.err"
echo "$out"
