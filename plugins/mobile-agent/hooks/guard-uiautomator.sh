#!/usr/bin/env bash
# PreToolUse / Bash — avisa quando `uiautomator dump` escreve em arquivo.
#
# Por que: `uiautomator dump /sdcard/ui.xml` falha em silencio com alguma
# frequencia. Quando falha, o arquivo anterior continua la, voce le o XML da
# rodada PASSADA e conclui que a tela travou quando ela ja mudou. Custa um
# diagnostico inteiro de "app congelado" que nao existe.
#
# `adb exec-out uiautomator dump /dev/tty` traz pelo stdout, sem arquivo
# intermediario e sem estado velho.
set -uo pipefail

input=$(cat) || exit 0
cmd=$(jq -r '.tool_input.command // empty' <<<"$input" 2>/dev/null) || exit 0
[[ -n "$cmd" ]] || exit 0

grep -q 'uiautomator[[:space:]]\+dump' <<<"$cmd" || exit 0
# Ja esta na forma correta: nada a dizer.
grep -q '/dev/tty' <<<"$cmd" && exit 0

jq -n '{
  hookSpecificOutput: {
    hookEventName: "PreToolUse",
    additionalContext: (
      "`uiautomator dump` para ARQUIVO falha em silencio de vez em quando, e o " +
      "arquivo antigo permanece — voce le a arvore da rodada anterior e conclui " +
      "que a tela travou. Prefira `adb exec-out uiautomator dump /dev/tty`, que " +
      "vem pelo stdout e nao tem estado velho.\n" +
      "E saiba do limite: superficie de GL (MapLibre, mapas, video, WebView) NAO " +
      "aparece na arvore de acessibilidade, entao um dump vazio ali nao significa " +
      "app travado. Para essas telas o caminho e visual — `android screen capture " +
      "--annotate` mais `android screen resolve --screenshot <png> --string \"tap #N\"`. " +
      "Repare em `--screenshot`: a doc do proprio skill do Google diz `--screen`, " +
      "que o binario rejeita."
    )
  }
}' 2>/dev/null || exit 0
exit 0
