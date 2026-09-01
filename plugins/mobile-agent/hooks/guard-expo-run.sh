#!/usr/bin/env bash
# PreToolUse / Bash — avisa que `expo run:<plataforma>` nao prebuilda quando o
# diretorio nativo ja existe.
#
# Por que: a condicao e literal em @expo/cli — se o diretorio da plataforma
# existe, a funcao retorna sem prebuildar, sem aviso. Mudanca em app.json, em
# config plugin ou em icone e ignorada em silencio, e o build responde
# BUILD SUCCESSFUL em segundos. Voce conclui que a mudanca nao fez efeito e vai
# depurar o lugar errado.
#
# So dispara quando o diretorio nativo REALMENTE existe no projeto: sem ele o
# prebuild roda sozinho e nao ha o que avisar.
set -uo pipefail

input=$(cat) || exit 0
cmd=$(jq -r '.tool_input.command // empty' <<<"$input" 2>/dev/null) || exit 0
[[ -n "$cmd" ]] || exit 0

grep -qE 'expo[[:space:]]+run:(android|ios)' <<<"$cmd" || exit 0
# Ja veio com prebuild explicito na mesma linha: nada a dizer.
grep -q 'prebuild' <<<"$cmd" && exit 0

cwd=$(jq -r '.cwd // empty' <<<"$input" 2>/dev/null) || cwd=""
plat="android"
grep -q 'run:ios' <<<"$cmd" && plat="ios"
[[ -n "$cwd" && -d "$cwd/$plat" ]] || exit 0

jq -n --arg p "$plat" '{
  hookSpecificOutput: {
    hookEventName: "PreToolUse",
    additionalContext: (
      "O diretorio `" + $p + "/` ja existe neste projeto, e nesse caso " +
      "`expo run:" + $p + "` NAO roda o prebuild — a condicao e literal no " +
      "@expo/cli e nao emite aviso. Mudanca em app.json, em config plugin ou em " +
      "icone sera ignorada em silencio, e o build vai responder BUILD SUCCESSFUL " +
      "em segundos.\n" +
      "Se voce mexeu em alguma dessas coisas, rode antes:\n" +
      "  npx expo prebuild --platform " + $p + " --clean\n" +
      "Se mexeu so em JS/TS, pode seguir: o Fast Refresh cobre e nao ha o que " +
      "regenerar."
    )
  }
}' 2>/dev/null || exit 0
exit 0
