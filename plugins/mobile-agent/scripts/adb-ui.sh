#!/usr/bin/env bash
# Automacao de UI por TEXTO — inspecionar e tocar a tela sem ler screenshot.
#
#   adb-ui.sh dump                lista rotulo + bounds da tela atual
#   adb-ui.sh tap "Continuar"     toca o centro do melhor no que casa
#   adb-ui.sh tapxy 720 803       toca coordenada absoluta
#   adb-ui.sh type "ABC123"       digita texto
#   adb-ui.sh esc                 fecha o teclado
#   adb-ui.sh shot [saida.jpg]    screenshot ja reduzido, seguro de ler
#
# Com mais de um aparelho conectado, exporte ANDROID_SERIAL — o adb respeita.
#
# ── Duas decisoes que parecem detalhe e nao sao ──────────────────────────
#
# 1. O dump vem por `exec-out ... /dev/tty`, nao por arquivo. `uiautomator dump
#    /sdcard/ui.xml` falha em silencio de vez em quando, e o arquivo da rodada
#    anterior continua la — voce le a arvore velha e conclui que a tela travou
#    quando ela ja mudou. Pelo stdout nao ha estado para ficar velho.
#
# 2. `esc` manda keyevent 111, nao 4 (BACK). Num app React Native, BACK sem
#    teclado no ar dispara a navegacao para tras; se nao ha tela para voltar,
#    alguns apps abrem um erro em tela cheia que bloqueia o resto do fluxo.
#    ESC fecha o teclado e nao navega.
set -euo pipefail

AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PARSER="$AQUI/adb_ui.py"

morre() { printf '%s\n' "$*" >&2; exit 1; }

uso() { sed -n '3,9p' "$0" | sed 's/^# \?//' >&2; }

# Sem subcomando valido, mostre o uso — pedir ajuda nao pode exigir aparelho.
case "${1:-}" in
  dump|tap|tapxy|type|esc|shot) ;;
  *) uso; exit 2 ;;
esac

command -v adb >/dev/null 2>&1 || morre "adb nao esta no PATH."
[[ -f "$PARSER" ]] || morre "parser ausente: $PARSER"

devices=$(adb devices 2>/dev/null | grep -cE '\sdevice$' || true)
case "$devices" in
  0) morre "Nenhum aparelho conectado. \`adb devices\` para conferir." ;;
  1) ;;
  *) [[ -n "${ANDROID_SERIAL:-}" ]] || morre \
       "$devices aparelhos conectados. Exporte ANDROID_SERIAL para escolher." ;;
esac

dump() { adb exec-out uiautomator dump /dev/tty 2>/dev/null; }

# Um dump que volta sem nenhum no com rotulo quase nunca significa app travado:
# superficie de GL (mapa, video, WebView, canvas) simplesmente nao aparece na
# arvore de acessibilidade. Dizer isso aqui evita o diagnostico errado.
sem_arvore() {
  printf '%s\n' \
    "A arvore de acessibilidade voltou vazia nesta tela." \
    "" \
    "Isso normalmente NAO e app travado. Superficie de GL — mapa, video," \
    "WebView, canvas — nao aparece no dump do UI Automator." \
    "" \
    "Caminho visual, se o CLI \`android\` estiver instalado:" \
    "  android screen capture --annotate -o shot.png" \
    "  adb shell input \$(android screen resolve --screenshot shot.png --string \"tap #N\")" \
    "" \
    "Sem ele, sobra coordenada absoluta (\`tapxy\`) e verificacao por cor de pixel." >&2
}

case "${1:-}" in
  dump)
    saida=$(dump | python3 "$PARSER" list)
    if [[ -z "$saida" ]]; then sem_arvore; exit 3; fi
    printf '%s\n' "$saida"
    ;;
  tap)
    [[ $# -ge 2 ]] || morre "uso: adb-ui.sh tap <texto>"
    arvore=$(dump)
    xy=$(printf '%s' "$arvore" | python3 "$PARSER" find "$2") || xy=""
    if [[ -z "$xy" ]]; then
      if [[ -z "$(printf '%s' "$arvore" | python3 "$PARSER" list)" ]]; then
        sem_arvore
      else
        printf 'Nao achei %s na tela. `adb-ui.sh dump` mostra o que ha.\n' "$2" >&2
      fi
      exit 3
    fi
    printf 'tap %s -> %s\n' "$2" "$xy"
    # shellcheck disable=SC2086  # xy e "X Y", dois argumentos de proposito.
    adb shell input tap $xy
    ;;
  tapxy)
    [[ $# -ge 3 ]] || morre "uso: adb-ui.sh tapxy <x> <y>"
    adb shell input tap "$2" "$3"
    ;;
  type)
    [[ $# -ge 2 ]] || morre "uso: adb-ui.sh type <texto>"
    # `adb shell` entrega a linha ao shell do APARELHO, que redivide por
    # espaco e interpreta `;`, `&`, `$`. Sem tratar isso, `type "ABC 123"`
    # digita so "ABC" e some com o resto sem erro nenhum. Entao: espaco vira
    # %s (o `input text` aceita um argumento so) e o texto vai entre aspas
    # simples, com as aspas simples internas escapadas.
    texto=${2//\'/\'\\\'\'}
    texto=${texto// /%s}
    # Se mesmo assim o app recarregar sozinho no meio da digitacao, ai sim
    # suspeite de atalho de menu de desenvolvedor: em build de dev, certas
    # teclas sao atalho. Digite em pedacos, cortando antes da tecla.
    adb shell input text "'$texto'"
    ;;
  esc)
    adb shell input keyevent 111
    ;;
  shot)
    destino="${2:-shot.jpg}"
    tmp=$(mktemp --suffix=.png)
    trap 'rm -f "$tmp"' EXIT
    adb exec-out screencap -p > "$tmp" 2>/dev/null
    [[ -s "$tmp" ]] || morre "screencap voltou vazio."
    # Reduzir nao e estetica: um screenshot cheio tem alguns MB, e ler isso
    # direto numa sessao de agente e o caminho conhecido para derrubar o
    # processo por memoria.
    # O destino precisa ser absoluto: sem barra no caminho, o vipsthumbnail
    # escreve ao lado da ENTRADA — que aqui esta em /tmp — e nao no diretorio
    # de trabalho. O arquivo sairia em /tmp e este script imprimiria um caminho
    # que nao existe.
    case "$destino" in /*) abs="$destino" ;; *) abs="$PWD/$destino" ;; esac
    if command -v vipsthumbnail >/dev/null 2>&1; then
      vipsthumbnail "$tmp" --size 640x -o "${abs}[Q=85]" 2>/dev/null
      [[ -s "$abs" ]] || morre "vipsthumbnail nao escreveu $abs."
    elif command -v magick >/dev/null 2>&1; then
      magick "$tmp" -resize 640x "$destino"
    else
      cp "$tmp" "${destino%.jpg}.png"
      destino="${destino%.jpg}.png"
      printf 'Sem vipsthumbnail nem magick: salvei o PNG cheio. Cuidado ao ler.\n' >&2
    fi
    printf '%s\n' "$destino"
    ;;
  *)
    morre "subcomando nao tratado: $1"
    ;;
esac
