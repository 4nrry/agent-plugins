#!/usr/bin/env bash
# PreToolUse / Bash — avisa quando `vipsthumbnail -o NOME` vai gravar no lugar errado.
#
# Por que: o `-o` do vipsthumbnail e um FORMATO de nome, nao um caminho de saida.
# Sem barra, o arquivo nasce no diretorio do arquivo de ENTRADA, nao no cwd.
# Observado nesta colecao: `vipsthumbnail repo/public/foto.jpg -s 480 -o foto-480.png`
# rodado de um scratch deixou `foto-480.png` untracked dentro do repositorio e o
# scratch vazio; o comando seguinte, que esperava o arquivo no cwd, falhou com
# "No such file" e o arquivo perdido so apareceu no `git status` de outro projeto.
set -uo pipefail

input=$(cat) || exit 0
cmd=$(jq -r '.tool_input.command // empty' <<<"$input" 2>/dev/null) || exit 0
[[ -n "$cmd" ]] || exit 0

# Interessa so `-o`/`--output` cujo valor nao tem barra. Valor com barra e caminho
# explicito e faz o que parece.
grep -qE '(^|[;&|[:space:]])vipsthumbnail[[:space:]].*(-o|--output)[[:space:]=]+[^/[:space:]"'"'"']+([[:space:]]|$)' <<<"$cmd" || exit 0

jq -n '{
  hookSpecificOutput: {
    hookEventName: "PreToolUse",
    additionalContext: (
      "`vipsthumbnail -o NOME` sem barra grava NOME no diretorio do arquivo de " +
      "ENTRADA, nao no diretorio atual. Se a entrada esta num repositorio, o " +
      "thumbnail nasce la dentro, untracked, e o cwd continua vazio. Passe um " +
      "caminho com diretorio em -o (por exemplo `-o /tmp/x/%s-480.png` ou " +
      "`-o ./saida.png`), ou use `magick IN -resize 480x480 OUT`."
    )
  }
}'
