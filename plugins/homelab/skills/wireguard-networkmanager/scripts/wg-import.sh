#!/usr/bin/env bash
# Importa uma config WireGuard (.conf de Proton, Mullvad, IVPN, AirVPN...) para o
# NetworkManager, de modo que ela apareca no applet de rede do Plasma.
#
#   ./wg-import.sh caminho/para/arquivo.conf [Prefixo]
#
# O nome que aparece no applet e derivado do rotulo do servidor gravado dentro
# do proprio .conf -- o comentario sob [Peer], ex. "# US-FREE#63" -- prefixado
# pelo provedor: "Proton US-FREE#63". Assim o nome bate com o painel do
# provedor, que e onde voce compara carga e etiqueta IPv6, e nao sobra nome
# digitado a mao para divergir de uma importacao para outra.
#
# Depois: liga e desliga pelo applet, ou por
#   nmcli connection up "Nome bonito"   /   nmcli connection down "Nome bonito"
set -euo pipefail

CONF=${1:-}
PREFIX=${2:-}
NICE_NAME=""

die() { printf 'erro: %s\n' "$1" >&2; exit 1; }

[ -n "$CONF" ] || die "uso: $0 arquivo.conf [Prefixo]"
[ -f "$CONF" ] || die "arquivo nao encontrado: $CONF"
grep -q '^\[Interface\]' "$CONF" || die "nao parece uma config WireGuard (falta [Interface]): $CONF"
grep -q '^\[Peer\]'      "$CONF" || die "nao parece uma config WireGuard (falta [Peer]): $CONF"

# A config traz chave privada em texto puro e costuma vir do navegador com 644,
# legivel por qualquer usuario da maquina.
chmod 600 "$CONF"

# Se a rede tem IPv6 e a config so roteia IPv4, todo trafego v6 (Google, YouTube,
# qualquer coisa atras da Cloudflare) sai por fora do tunel com o IP real. Isso e
# silencioso: a VPN "funciona", o teste de IPv4 passa, e mesmo assim vaza.
TEM_V6_LOCAL=$(ip -6 -brief address show scope global 2>/dev/null | grep -cv -e '^wg' -e '^tailscale' || true)
if [ "$TEM_V6_LOCAL" -gt 0 ] && ! grep -i '^AllowedIPs' "$CONF" | grep -q '::/0'; then
    echo "AVISO: sua rede tem IPv6 global, mas esta config so roteia IPv4 (sem ::/0)."
    echo "       Todo o trafego IPv6 vai continuar saindo com seu IP real."
    echo "       Prefira gerar a config em um servidor marcado como IPv6 pelo provedor."
    printf '       Importar mesmo assim? [s/N] '
    read -r RESP
    case "$RESP" in
        s|S|y|Y) : ;;
        *) die "cancelado" ;;
    esac
fi

ORIG=$(basename "$CONF" .conf)

# O provedor grava o nome do servidor no .conf, como primeiro comentario depois
# de [Peer]. Derivar dali em vez de aceitar um nome digitado e o que mantem a
# nomenclatura estavel: o applet passa a mostrar exatamente o que o painel do
# provedor mostra, sem depender de quem importou lembrar do formato.
SERVER_LABEL=$(awk '/^\[Peer\]/ {p=1; next} p && /^#/ {sub(/^#[[:space:]]*/, ""); print; exit}' "$CONF")
if [ -n "$SERVER_LABEL" ]; then
    NICE_NAME=$(printf '%s %s' "$PREFIX" "$SERVER_LABEL" | sed 's/^[[:space:]]*//; s/[[:space:]]*$//')
elif [ -n "$PREFIX" ]; then
    echo "AVISO: o .conf nao traz rotulo de servidor sob [Peer]; usando '$PREFIX'."
    NICE_NAME=$PREFIX
fi

# O NM exige que o nome do arquivo seja um nome de interface valido: no maximo 15
# caracteres, sem caracteres especiais. Configs geradas por provedor estouram isso
# com facilidade ("Book4Ultra-US-FREE-122"), entao importamos de uma copia curta.
BASE=$(printf '%s' "$ORIG" | tr -c 'a-zA-Z0-9_-' '-' | cut -c1-15)
[ -n "$BASE" ] || die "nao consegui derivar um nome de interface de '$ORIG'"

if nmcli -t -f NAME connection show | grep -Fxq "$BASE"; then
    die "ja existe uma conexao '$BASE'. Remova com: nmcli connection delete '$BASE'"
fi
if [ -n "$NICE_NAME" ] && nmcli -t -f NAME connection show | grep -Fxq "$NICE_NAME"; then
    die "ja existe uma conexao '$NICE_NAME'. Remova com: nmcli connection delete '$NICE_NAME'"
fi

IMPORT_FROM=$CONF
TMPDIR_WG=""
if [ "$BASE" != "$ORIG" ]; then
    echo "nome ajustado ao limite do NM: '$ORIG' -> '$BASE'"
    TMPDIR_WG=$(mktemp -d); chmod 700 "$TMPDIR_WG"
    IMPORT_FROM="$TMPDIR_WG/$BASE.conf"
    (umask 077; cp "$CONF" "$IMPORT_FROM")
fi
# O "return 0" nao e decorativo: sob "set -e", um trap EXIT que termina em
# comando falso faz o script sair 1. Com o .conf ja dentro do limite de 15
# caracteres nenhum TMPDIR e criado, o && curto-circuita falso, e um import
# bem-sucedido reportava erro.
cleanup() { [ -n "$TMPDIR_WG" ] && [ -d "$TMPDIR_WG" ] && rm -rf "$TMPDIR_WG"; return 0; }
trap cleanup EXIT

echo "== IP publico antes =="
IP_ANTES=$(curl -fsS --max-time 10 https://api.ipify.org || echo "(nao consegui consultar)")
echo "$IP_ANTES"

echo
echo "== importando '$BASE' =="
nmcli connection import type wireguard file "$IMPORT_FROM"

# O NM ativa a conexao sozinho no import. Desligar o autoconnect evita que ela
# suba no boot sem voce pedir: este caminho nao tem kill switch, entao e melhor
# que a VPN exista so quando escolhida.
nmcli connection modify "$BASE" connection.autoconnect no

if [ -n "$NICE_NAME" ]; then
    nmcli connection modify "$BASE" connection.id "$NICE_NAME"
    BASE=$NICE_NAME
fi

echo
echo "== estado =="
nmcli -t -f NAME,TYPE,DEVICE,STATE connection show --active | grep -F "$BASE" \
    || echo "(inativa -- suba com: nmcli connection up \"$BASE\")"

echo
echo "== IP publico depois =="
# O handshake e a troca de DNS levam alguns segundos. Consultar imediatamente da
# falso negativo -- parece que a VPN nao funcionou quando ela so nao assentou.
IP_DEPOIS="(nao consegui consultar)"
for _ in 1 2 3 4 5 6; do
    if RESP=$(curl -fsS --max-time 8 https://api.ipify.org 2>/dev/null); then
        IP_DEPOIS=$RESP
        break
    fi
    sleep 3
done
echo "$IP_DEPOIS"

echo
if [ "$IP_ANTES" != "$IP_DEPOIS" ] && [ "$IP_DEPOIS" != "(nao consegui consultar)" ]; then
    echo "OK: o trafego esta saindo pelo tunel ($IP_ANTES -> $IP_DEPOIS)."
else
    echo "ATENCAO: o IP publico nao mudou. Rode wg-check.sh para investigar."
fi

echo
echo "A conexao '$BASE' agora aparece no applet de rede do Plasma."
echo "Rode wg-check.sh para conferir IPv6 e DNS antes de confiar nela."
