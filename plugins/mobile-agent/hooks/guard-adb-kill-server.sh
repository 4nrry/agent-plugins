#!/usr/bin/env bash
# PreToolUse / Bash — avisa antes de `adb kill-server`.
#
# Por que: num retry, `adb kill-server` derruba a conexao inteira e o sintoma
# vira "o cabo esta ruim" ou "o aparelho desconectou". Pior num ambiente com
# emulador: reiniciar o servidor adb leva junto TODOS os `adb reverse`, de todas
# as sessoes, e o app perde a stack sem nada nos logs dele.
#
# Este hook nunca bloqueia. `adb kill-server` e legitimo quando o servidor
# travou de verdade; o que ele evita e o reflexo de rodar isso ao primeiro erro.
set -uo pipefail

input=$(cat) || exit 0
cmd=$(jq -r '.tool_input.command // empty' <<<"$input" 2>/dev/null) || exit 0
[[ -n "$cmd" ]] || exit 0

# Reconfere: o `if` do hooks.json ja filtrou, mas um harness que o ignore
# mandaria todo comando Bash para ca.
grep -qE '(^|[;&|[:space:]])adb[[:space:]]+kill-server([[:space:]]|$)' <<<"$cmd" || exit 0

jq -n '{
  hookSpecificOutput: {
    hookEventName: "PreToolUse",
    additionalContext: (
      "adb kill-server derruba TODOS os `adb reverse` da maquina, de todas as sessoes — " +
      "nao so as suas. O app perde a stack e o sintoma imita backend fora do ar.\n" +
      "Antes: `adb devices` diz se o servidor responde, e `adb reverse --list` " +
      "mostra o que voce vai perder. Se for so um device sumido, `adb reconnect` " +
      "resolve sem derrubar o servidor.\n" +
      "Depois, se seguir: reaplique os tuneis que estavam de pe."
    )
  }
}' 2>/dev/null || exit 0
exit 0
