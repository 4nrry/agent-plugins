#!/usr/bin/env bash
# PreToolUse / Bash — avisa quando um `pkill`/`pgrep` casa a propria linha.
#
# Por que: `pkill -f foo` dentro de um comando que contem `foo` mata o proprio
# shell. O truque do colchete nao salva — `pgrep -f '[f]oo'` ainda casa se a
# palavra aparecer em qualquer outro ponto da linha, inclusive dentro de um
# echo. Nenhum linter pega isso.
#
# Nesta sessao o mesmo erro produziu um falso positivo caro: um `pgrep -f
# GradleDaemon` casou o proprio comando e reportou daemon vazado onde nao havia.
set -uo pipefail

input=$(cat) || exit 0
cmd=$(jq -r '.tool_input.command // empty' <<<"$input" 2>/dev/null) || exit 0
[[ -n "$cmd" ]] || exit 0

# So interessa a forma que casa por linha de comando inteira: -f (ou --full).
# A flag quase nunca vem colada ao nome — `pkill -9 -f node` e a forma mais
# comum, e e justamente a que mata — entao aceite flags no meio do caminho.
grep -qE '(^|[;&|[:space:]])(pkill|pgrep)([[:space:]]+-[^[:space:]]+)*[[:space:]]+(-[a-zA-Z]*f([[:space:]]|$)|--full)' <<<"$cmd" || exit 0

jq -n '{
  hookSpecificOutput: {
    hookEventName: "PreToolUse",
    additionalContext: (
      "`pkill -f` / `pgrep -f` casam contra a linha de comando INTEIRA, incluindo " +
      "a deste proprio comando. Se o padrao aparece aqui — mesmo dentro de um " +
      "echo, de um comentario ou de um caminho — voce casa a si mesmo: com pkill " +
      "isso mata o shell, com pgrep isso reporta um processo que nao existe.\n" +
      "O truque do colchete NAO resolve. Alternativas que nao se auto-casam: " +
      "`pkill -x <nome-exato>`, ou `pgrep -x`, ou ler o cmdline de /proc e filtrar " +
      "por PID obtido antes.\n" +
      "E a regra que vem junto: nao mate processo que voce nao subiu — emulador, " +
      "Metro, container e dev server podem ser de outra sessao ou do usuario."
    )
  }
}' 2>/dev/null || exit 0
exit 0
