#!/usr/bin/env bash
# PreToolUse / Bash — avisa quando `scrcpy` vai rodar sem `ADB` definido e ha
# mais de um adb ao alcance.
#
# Por que: o scrcpy usa o adb da variavel ADB ou o primeiro do PATH (man,
# secao ENVIRONMENT). Se esse nao for o adb que o Metro, o emulador e o
# `adb reverse` ja usam, sao dois servidores de versoes diferentes — e o
# segundo mata o primeiro, levando os tuneis. O sintoma aparece no APP ("nao
# foi possivel carregar"), nao no espelho.
#
# So fala quando ha de fato dois candidatos: ADB ausente, o adb do SDK existe,
# e ou ha outro adb no PATH ou o proprio scrcpy traz um ao lado dele.
set -uo pipefail

input=$(cat) || exit 0
cmd=$(jq -r '.tool_input.command // empty' <<<"$input" 2>/dev/null) || exit 0
[[ -n "$cmd" ]] || exit 0

grep -qE '(^|[;&|[:space:]])scrcpy([[:space:]]|$)' <<<"$cmd" || exit 0
# ADB fixado na propria linha, ou herdado do ambiente: nada a dizer.
grep -qE '(^|[[:space:]])ADB=' <<<"$cmd" && exit 0
[[ -n "${ADB:-}" ]] && exit 0

sdk="${ANDROID_HOME:-$HOME/Android/Sdk}/platform-tools/adb"
[[ -x "$sdk" ]] || exit 0

outro=""
exe=$(command -v scrcpy 2>/dev/null || true)
if [[ -n "$exe" ]]; then
  real=$(readlink -f "$exe" 2>/dev/null || printf '%s' "$exe")
  [[ -x "$(dirname "$real")/adb" ]] && outro="$(dirname "$real")/adb"
fi
if [[ -z "$outro" ]]; then
  primeiro=$(command -v adb 2>/dev/null || true)
  if [[ -n "$primeiro" ]]; then
    [[ "$(readlink -f "$primeiro")" != "$(readlink -f "$sdk")" ]] && outro="$primeiro"
  fi
fi
[[ -n "$outro" ]] || exit 0

jq -n --arg sdk "$sdk" --arg outro "$outro" '{
  hookSpecificOutput: {
    hookEventName: "PreToolUse",
    additionalContext: (
      "scrcpy sem ADB definido: ele vai usar `" + $outro + "`, e o resto da " +
      "sessao (Metro, emulador, adb reverse) usa `" + $sdk + "`. Dois adb de " +
      "versoes diferentes reiniciam o servidor um do outro e derrubam os tuneis; " +
      "o sintoma aparece no app, nao no espelho.\n" +
      "Prefixe: ADB=" + $sdk + " scrcpy ... (ou fixe isso num wrapper; skill " +
      "espelhar-celular)."
    )
  }
}' 2>/dev/null || exit 0
exit 0
