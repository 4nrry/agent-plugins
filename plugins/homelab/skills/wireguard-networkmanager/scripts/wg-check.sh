#!/usr/bin/env bash
# Checks whether a NetworkManager-managed WireGuard tunnel really carries the
# traffic, and whether anything escapes around it.
#
#   ./wg-check.sh
#
# Checks the three leaks that matter in this setup: IPv4, IPv6 and DNS.
# Exits 1 on a leak, 0 when everything is inside the tunnel.
set -uo pipefail

FAILED=0

echo "== active wireguard connections =="
ACTIVE=$(nmcli -t -f NAME,TYPE,DEVICE,STATE connection show --active | awk -F: '$2=="wireguard"')
if [ -z "$ACTIVE" ]; then
    echo "none. Nothing to check."
    exit 0
fi
printf '%s\n' "$ACTIVE"
DEV=$(printf '%s' "$ACTIVE" | head -1 | cut -d: -f3)

echo
echo "== did the tunnel exchange packets? (rx zero = no handshake) =="
ip -s link show "$DEV" 2>/dev/null | tail -4 | sed 's/^/  /'

echo
echo "== public IPv4 =="
IP4=$(curl -4 -fsS --max-time 10 https://api.ipify.org 2>/dev/null || echo "")
if [ -z "$IP4" ]; then
    echo "  could not query it (no DNS or no route?)"
    FAILED=1
else
    echo "  $IP4"
fi

echo
echo "== IPv6: does the link have its own IPv6? =="
# Global addresses of the physical interfaces -- if one of them shows up as the
# public IP, v6 traffic is leaving outside the tunnel.
LOCAL_V6=$(ip -6 -brief address show scope global 2>/dev/null \
    | grep -v -e "^$DEV" -e '^tailscale' \
    | awk '{for(i=3;i<=NF;i++) print $i}' | cut -d/ -f1)

if [ -z "$LOCAL_V6" ]; then
    echo "  the network has no IPv6 -- nothing to leak over v6"
else
    printf '  the network has global IPv6. Querying the public IPv6...\n'
    IP6=$(curl -6 -fsS --max-time 10 https://api64.ipify.org 2>/dev/null || echo "")
    if [ -z "$IP6" ]; then
        echo "  no IPv6 egress right now (the tunnel may be blocking it -- that is safe)"
    elif printf '%s\n' "$LOCAL_V6" | grep -Fxq "$IP6"; then
        echo "  IPv6 LEAK: the world sees $IP6, which is your network's address."
        echo "  Likely cause: the config's AllowedIPs does not include ::/0."
        FAILED=1
    else
        echo "  $IP6 -- differs from the local address, inside the tunnel"
    fi
fi

echo
echo "== DNS: who answers the queries =="
# With the tunnel up, systemd-resolved should drop the DNS scope from the
# physical interfaces and send everything through the tunnel link. If a
# physical one still has an active DNS scope, queries may go to the ISP.
# Only interfaces that carry a default route outside the tunnel matter -- that
# is where a query would escape. Filtering by type does not work: container
# veths present as ethernet and flood the output.
PHYSICAL=$( { ip -4 route show default; ip -6 route show default; } 2>/dev/null \
    | awk '{for(i=1;i<=NF;i++) if($i=="dev") print $(i+1)}' \
    | grep -v -e "^$DEV\$" -e '^tailscale' | sort -u)

for LINK in $PHYSICAL; do
    SCOPE=$(resolvectl status "$LINK" 2>/dev/null | awk -F': *' '/Current Scopes/{print $2; exit}')
    ROUTE=$(resolvectl status "$LINK" 2>/dev/null | awk -F': *' '/Default Route/{print $2; exit}')
    printf '  %-12s scope=%s dns-default-route=%s\n' "$LINK" "${SCOPE:-?}" "${ROUTE:-?}"
    if [ "${SCOPE:-none}" != "none" ] && [ "${ROUTE:-no}" = "yes" ]; then
        echo "    WARNING: this interface still resolves DNS on its own"
        FAILED=1
    fi
done
resolvectl status "$DEV" 2>/dev/null | awk -F': *' '/DNS Servers/{print "  tunnel uses DNS: " $2; exit}'

echo
if [ "$FAILED" -eq 0 ]; then
    echo "OK: IPv4, IPv6 and DNS are all inside the tunnel."
else
    echo "Something is escaping -- see the warnings above."
fi
exit "$FAILED"
