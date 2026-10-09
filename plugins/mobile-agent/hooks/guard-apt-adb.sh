#!/usr/bin/env bash
# PreToolUse / Bash — avisa antes de `apt install scrcpy` (ou `adb`): o pacote
# do Ubuntu instala um SEGUNDO adb em /usr/bin, na frente do adb do SDK.
#
# Por que: o pacote `scrcpy` do Ubuntu depende do pacote `adb` (documentado).
# A doc do React Native manda ANEXAR o platform-tools ao PATH, entao /usr/bin
# vence, e dois adb de versoes diferentes reiniciam o servidor a cada chamada
# ("adb server version doesn't match this client; killing..."). Isso leva
# junto todos os `adb reverse` e a conexao sem fio — o mesmo estrago do
# `adb kill-server`, so que silencioso e repetido.
#
# Nunca bloqueia: instalar e decisao do usuario. Avisa so quando ha um adb do
# SDK para ser sombreado; sem SDK na maquina, o adb do apt e o unico, e nao ha
# o que dizer.
set -uo pipefail

input=$(cat) || exit 0
cmd=$(jq -r '.tool_input.command // empty' <<<"$input" 2>/dev/null) || exit 0
[[ -n "$cmd" ]] || exit 0

grep -qE '(^|[;&|[:space:]])(sudo[[:space:]]+)?(apt|apt-get)[[:space:]]+install([[:space:]]|$)' <<<"$cmd" || exit 0
grep -qE '(^|[[:space:]])(scrcpy|adb|android-tools-adb)([[:space:]]|$)' <<<"$cmd" || exit 0

sdk="${ANDROID_HOME:-$HOME/Android/Sdk}/platform-tools/adb"
[[ -x "$sdk" ]] || exit 0

jq -n --arg sdk "$sdk" '{
  hookSpecificOutput: {
    hookEventName: "PreToolUse",
    additionalContext: (
      "O pacote `scrcpy` do apt depende do pacote `adb`, que vai para /usr/bin — " +
      "ANTES do adb do SDK (" + $sdk + ") no PATH que a doc do React Native " +
      "manda montar. Dois adb de versoes diferentes reiniciam o servidor a cada " +
      "chamada e derrubam todos os `adb reverse` e a conexao sem fio.\n" +
      "Alternativa sem segundo adb: o tarball oficial do release do scrcpy, com " +
      "um wrapper que exporta ADB=" + $sdk + " (skill espelhar-celular).\n" +
      "Se seguir com o apt: confira `which -a adb` depois e deixe UM na frente."
    )
  }
}' 2>/dev/null || exit 0
exit 0
