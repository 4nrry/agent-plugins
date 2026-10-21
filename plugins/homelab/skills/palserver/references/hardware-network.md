# Hardware, network and measuring

## Contents
- Requirements
- Measuring
- Ports
- Letting players in
- Quick diagnostics

## Requirements

| Item | Official |
|---|---|
| CPU | "4 Core +" |
| RAM | "16GB Recommended for larger than 32GB. 8GB is also bootable" |
| Disk | SSD — "Low-performance storage may corrupt saved data" |
| OS | 64-bit Windows or Linux ("Ubuntu, AlmaLinux etc...") |
| Network | "UDP Port 8211 (Default, Changeable)" |

Palworld wants a strong single core; more slow cores do not compensate. An
HDD or eMMC stalls everything on frequent saves. Running the game client and
the server on one machine works but adds both loads.

## Measuring

Uptime does not predict RSS; load does. Record players online with every
reading, or the series measures the wrong variable.

```bash
# the process now
ps -o pid,etime,rss,%cpu -p "$(pgrep -x PalServer-Linux)"

# a series, not a point
while :; do
  printf '%s %s\n' "$(date +%s)" \
    "$(ps -o rss= -p "$(pgrep -x PalServer-Linux)")"
  sleep 300
done >> ~/palworld-rss.log
```

**Process uptime does not prove continuity.** A crash restarts the process
under `Restart=on-failure` and resets the curve silently. Before concluding
anything, count the boots:

```bash
journalctl --user -u palworld | grep -c 'Game version is'   # boots
journalctl --user -u palworld | grep 'Signal 11 caught'     # crashes
```

The REST `metrics` route also returns uptime, players and memory.

## Ports

| Port | Protocol | Needed |
|---|---|---|
| 8211 | UDP | Yes (game); changed with `-port=` |
| 27015 | UDP | No (Steam query); not configurable |
| 8212 | TCP | Only with the REST API; never exposed |
| 25575 | TCP | RCON only, deprecated |

## Letting players in

- **Mesh VPN** (Tailscale, Netbird, ZeroTier): nothing exposed, router
  untouched; players use the VPN IP on 8211. Each player installs the VPN.
- **Port forward** 8211/UDP: needs a fixed LAN IP (DHCP reservation) and DDNS
  if the public IP changes. `ServerPassword` becomes mandatory.
- **Community server** (`-publiclobby`): listed in-game; the only route for
  Xbox and PS5.

Behind CGNAT (a private IP at traceroute hop 2) a port forward cannot work;
use a mesh VPN, a community server or a VPS.

## Quick diagnostics

```bash
ss -ulnp | grep -E ':(8211|27015)\b'

# Anyone playing? Keepalive is hundreds of B/s; a real player is KB/s.
# Replace IFACE with the interface in use.
t1=$(awk '/IFACE/{print $10}' /proc/net/dev); sleep 8
t2=$(awk '/IFACE/{print $10}' /proc/net/dev); echo "TX: $(( (t2-t1)/8 )) B/s"
```
