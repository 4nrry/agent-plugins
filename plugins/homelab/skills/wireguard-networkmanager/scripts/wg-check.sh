#!/usr/bin/env bash
# Verifica se um tunel WireGuard gerenciado pelo NetworkManager esta de fato
# carregando o trafego, e se algo esta escapando por fora dele.
#
#   ./wg-check.sh
#
# Checa os tres vazamentos que importam nesse tipo de montagem: IPv4, IPv6 e DNS.
# Sai com 1 se encontrar vazamento, 0 se estiver tudo dentro do tunel.
set -uo pipefail

FALHOU=0

echo "== conexoes wireguard ativas =="
ATIVAS=$(nmcli -t -f NAME,TYPE,DEVICE,STATE connection show --active | awk -F: '$2=="wireguard"')
if [ -z "$ATIVAS" ]; then
    echo "nenhuma. Nada para verificar."
    exit 0
fi
printf '%s\n' "$ATIVAS"
DEV=$(printf '%s' "$ATIVAS" | head -1 | cut -d: -f3)

echo
echo "== o tunel trocou pacotes? (rx zerado = handshake nao aconteceu) =="
ip -s link show "$DEV" 2>/dev/null | tail -4 | sed 's/^/  /'

echo
echo "== IPv4 publico =="
IP4=$(curl -4 -fsS --max-time 10 https://api.ipify.org 2>/dev/null || echo "")
if [ -z "$IP4" ]; then
    echo "  nao consegui consultar (sem DNS ou sem rota?)"
    FALHOU=1
else
    echo "  $IP4"
fi

echo
echo "== IPv6: o link tem IPv6 proprio? =="
# Enderecos globais das interfaces fisicas -- se um deles aparecer como IP
# publico, o trafego v6 esta saindo por fora do tunel.
LOCAIS_V6=$(ip -6 -brief address show scope global 2>/dev/null \
    | grep -v -e "^$DEV" -e '^tailscale' \
    | awk '{for(i=3;i<=NF;i++) print $i}' | cut -d/ -f1)

if [ -z "$LOCAIS_V6" ]; then
    echo "  a rede nao tem IPv6 -- nao ha o que vazar por v6"
else
    printf '  a rede tem IPv6 global. Consultando o IPv6 publico...\n'
    IP6=$(curl -6 -fsS --max-time 10 https://api64.ipify.org 2>/dev/null || echo "")
    if [ -z "$IP6" ]; then
        echo "  sem saida IPv6 no momento (o tunel pode estar bloqueando -- isso e seguro)"
    elif printf '%s\n' "$LOCAIS_V6" | grep -Fxq "$IP6"; then
        echo "  VAZAMENTO IPv6: o mundo ve $IP6, que e o endereco da sua rede."
        echo "  Causa provavel: o AllowedIPs da config nao inclui ::/0."
        FALHOU=1
    else
        echo "  $IP6 -- diferente do endereco local, esta dentro do tunel"
    fi
fi

echo
echo "== DNS: quem esta respondendo as consultas =="
# Com o tunel de pe, o systemd-resolved deve tirar o escopo DNS das interfaces
# fisicas e mandar tudo pelo link do tunel. Se uma fisica ainda tem escopo DNS
# ativo, as consultas podem sair para o provedor de internet.
# So interessam as interfaces que carregam rota padrao fora do tunel -- e por elas
# que uma consulta escaparia. Filtrar por tipo nao serve: veth de container se
# apresenta como ethernet e enche a saida de ruido.
FISICAS=$( { ip -4 route show default; ip -6 route show default; } 2>/dev/null \
    | awk '{for(i=1;i<=NF;i++) if($i=="dev") print $(i+1)}' \
    | grep -v -e "^$DEV\$" -e '^tailscale' | sort -u)

for LINK in $FISICAS; do
    ESCOPO=$(resolvectl status "$LINK" 2>/dev/null | awk -F': *' '/Current Scopes/{print $2; exit}')
    ROTA=$(resolvectl status "$LINK" 2>/dev/null | awk -F': *' '/Default Route/{print $2; exit}')
    printf '  %-12s escopo=%s rota-padrao-dns=%s\n' "$LINK" "${ESCOPO:-?}" "${ROTA:-?}"
    if [ "${ESCOPO:-none}" != "none" ] && [ "${ROTA:-no}" = "yes" ]; then
        echo "    ATENCAO: esta interface ainda resolve DNS por conta propria"
        FALHOU=1
    fi
done
resolvectl status "$DEV" 2>/dev/null | awk -F': *' '/DNS Servers/{print "  tunel usa DNS: " $2; exit}'

echo
if [ "$FALHOU" -eq 0 ]; then
    echo "OK: IPv4, IPv6 e DNS estao todos dentro do tunel."
else
    echo "Algo esta escapando -- veja os avisos acima."
fi
exit "$FALHOU"
