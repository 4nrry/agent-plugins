#!/usr/bin/env bash
# UserPromptSubmit — quando o prompt menciona um jogo instalado, injeta o que
# a maquina sabe sobre ele: appid, buildid e data da ultima atualizacao.
#
# Por que hook e nao description: medicao deste proprio repositorio, no plugin
# agent-fleet, mediu trigger por `description` disparando em 2 de 30 execucoes
# que deveriam disparar, com recall por query entre 0,00 e 0,33, e nenhuma
# reescrita melhorou o score retido (bench/plugins/agent-fleet/results/2026-08-06-trigger-eval/).
# Skill que depende de ser lembrada nao e lembrada. Aqui o gatilho e casamento
# mecanico de string, nao persuasao do modelo.
#
# O casamento fica no Python de proposito: e a parte que produz falso positivo,
# entao e a parte coberta por --self-test, que o `just check` executa. Este
# script so passa a stdin adiante.
#
# NAO ha medicao de disparo deste hook ainda: nem taxa de acerto, nem falso
# positivo em prompt sem jogo. A escolha de casar o nome como frase inteira
# vem do raciocinio registrado no README, nao de um eval.
#
# Falha aberto, sempre exit 0: uma dica de versao que nao veio custa menos do
# que um prompt do usuario que nao passou.
set -uo pipefail

# Resolve pela propria localizacao em vez de ${CLAUDE_PLUGIN_ROOT}: funciona
# igual rodado pelo runner de hooks, na mao, ou de uma arvore copiada.
PLUGIN_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DETECTOR="$PLUGIN_ROOT/scripts/steam_games.py"

command -v jq >/dev/null 2>&1 || exit 0
command -v python3 >/dev/null 2>&1 || exit 0

prompt=$(jq -r '.prompt // empty' 2>/dev/null) || exit 0
[[ -n "$prompt" ]] || exit 0

if [[ ! -x "$DETECTOR" ]]; then
  echo "game-facts: $DETECTOR ausente ou sem bit de execucao — nada injetado" >&2
  exit 0
fi

saida=$(printf '%s' "$prompt" | python3 "$DETECTOR" --match-stdin 2>/dev/null) || exit 0
[[ -n "$saida" ]] || exit 0

printf '%s\n\nContexto completo, inclusive jogo fora da Steam e como achar a versao de marketing: %s/skills/game-versions/SKILL.md\n' \
  "$saida" "$PLUGIN_ROOT"
exit 0
