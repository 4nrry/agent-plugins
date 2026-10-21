#!/usr/bin/env bash
# Imports a WireGuard config (.conf from Proton, Mullvad, IVPN, AirVPN...) into
# NetworkManager, so it shows up in the Plasma network applet.
#
#   ./wg-import.sh path/to/file.conf [Prefix]
#
# The applet name is derived from the server label stored in the .conf itself
# -- the comment under [Peer], e.g. "# US-FREE#63" -- prefixed by the provider:
# "Proton US-FREE#63". The name then matches the provider's dashboard, where
# load and the IPv6 tag are compared, and no hand-typed name drifts between
# one import and the next.
#
# Afterwards: toggle from the applet, or with
#   nmcli connection up "Nice name"   /   nmcli connection down "Nice name"
set -euo pipefail

CONF=${1:-}
PREFIX=${2:-}
NICE_NAME=""

die() { printf 'error: %s\n' "$1" >&2; exit 1; }

[ -n "$CONF" ] || die "usage: $0 file.conf [Prefix]"
[ -f "$CONF" ] || die "file not found: $CONF"
grep -q '^\[Interface\]' "$CONF" || die "not a WireGuard config (no [Interface]): $CONF"
grep -q '^\[Peer\]'      "$CONF" || die "not a WireGuard config (no [Peer]): $CONF"

# The config holds a plaintext private key and usually arrives from the browser
# as 644, readable by every user on the machine.
chmod 600 "$CONF"

# If the network has IPv6 and the config routes only IPv4, all v6 traffic
# (Google, YouTube, anything behind Cloudflare) leaves outside the tunnel with
# the real IP. Silently: the VPN "works", the IPv4 test passes, and it leaks.
HAS_LOCAL_V6=$(ip -6 -brief address show scope global 2>/dev/null | grep -cv -e '^wg' -e '^tailscale' || true)
if [ "$HAS_LOCAL_V6" -gt 0 ] && ! grep -i '^AllowedIPs' "$CONF" | grep -q '::/0'; then
    echo "WARNING: your network has global IPv6, but this config routes only IPv4 (no ::/0)."
    echo "         All IPv6 traffic will keep leaving with your real IP."
    echo "         Prefer a config generated for a server the provider marks as IPv6."
    printf '         Import anyway? [y/N] '
    read -r ANSWER
    case "$ANSWER" in
        s|S|y|Y) : ;;
        *) die "cancelled" ;;
    esac
fi

ORIG=$(basename "$CONF" .conf)

# The provider writes the server name into the .conf as the first comment after
# [Peer]. Deriving it from there instead of accepting a typed name keeps naming
# stable: the applet shows exactly what the provider's dashboard shows, without
# relying on whoever imports to remember the format.
SERVER_LABEL=$(awk '/^\[Peer\]/ {p=1; next} p && /^#/ {sub(/^#[[:space:]]*/, ""); print; exit}' "$CONF")
if [ -n "$SERVER_LABEL" ]; then
    NICE_NAME=$(printf '%s %s' "$PREFIX" "$SERVER_LABEL" | sed 's/^[[:space:]]*//; s/[[:space:]]*$//')
elif [ -n "$PREFIX" ]; then
    echo "WARNING: the .conf has no server label under [Peer]; using '$PREFIX'."
    NICE_NAME=$PREFIX
fi

# NM requires the file name to be a valid interface name: at most 15
# characters, no special characters. Provider configs easily exceed that
# ("Book4Ultra-US-FREE-122"), so we import from a short-named copy.
BASE=$(printf '%s' "$ORIG" | tr -c 'a-zA-Z0-9_-' '-' | cut -c1-15)
[ -n "$BASE" ] || die "could not derive an interface name from '$ORIG'"

if nmcli -t -f NAME connection show | grep -Fxq "$BASE"; then
    die "a connection '$BASE' already exists. Remove it with: nmcli connection delete '$BASE'"
fi
if [ -n "$NICE_NAME" ] && nmcli -t -f NAME connection show | grep -Fxq "$NICE_NAME"; then
    die "a connection '$NICE_NAME' already exists. Remove it with: nmcli connection delete '$NICE_NAME'"
fi

IMPORT_FROM=$CONF
TMPDIR_WG=""
if [ "$BASE" != "$ORIG" ]; then
    echo "name shortened to NM's limit: '$ORIG' -> '$BASE'"
    TMPDIR_WG=$(mktemp -d); chmod 700 "$TMPDIR_WG"
    IMPORT_FROM="$TMPDIR_WG/$BASE.conf"
    (umask 077; cp "$CONF" "$IMPORT_FROM")
fi
# The "return 0" is not decorative: under "set -e", an EXIT trap ending in a
# false command makes the script exit 1. With the .conf already within 15
# characters no TMPDIR is created, the && short-circuits false, and a
# successful import reported an error.
cleanup() { [ -n "$TMPDIR_WG" ] && [ -d "$TMPDIR_WG" ] && rm -rf "$TMPDIR_WG"; return 0; }
trap cleanup EXIT

echo "== public IP before =="
IP_BEFORE=$(curl -fsS --max-time 10 https://api.ipify.org || echo "(could not query)")
echo "$IP_BEFORE"

echo
echo "== importing '$BASE' =="
nmcli connection import type wireguard file "$IMPORT_FROM"

# NM activates the connection on import. Turning autoconnect off keeps it from
# coming up at boot unasked: this path has no kill switch, so the VPN should
# exist only when chosen.
nmcli connection modify "$BASE" connection.autoconnect no

if [ -n "$NICE_NAME" ]; then
    nmcli connection modify "$BASE" connection.id "$NICE_NAME"
    BASE=$NICE_NAME
fi

echo
echo "== state =="
nmcli -t -f NAME,TYPE,DEVICE,STATE connection show --active | grep -F "$BASE" \
    || echo "(inactive -- bring it up with: nmcli connection up \"$BASE\")"

echo
echo "== public IP after =="
# The handshake and DNS switch take a few seconds. Querying immediately gives a
# false negative -- the VPN looks broken when it just has not settled.
IP_AFTER="(could not query)"
for _ in 1 2 3 4 5 6; do
    if ANSWER=$(curl -fsS --max-time 8 https://api.ipify.org 2>/dev/null); then
        IP_AFTER=$ANSWER
        break
    fi
    sleep 3
done
echo "$IP_AFTER"

echo
if [ "$IP_BEFORE" != "$IP_AFTER" ] && [ "$IP_AFTER" != "(could not query)" ]; then
    echo "OK: traffic is leaving through the tunnel ($IP_BEFORE -> $IP_AFTER)."
else
    echo "WARNING: the public IP did not change. Run wg-check.sh to investigate."
fi

echo
echo "The connection '$BASE' now shows in the Plasma network applet."
echo "Run wg-check.sh to check IPv6 and DNS before trusting it."
