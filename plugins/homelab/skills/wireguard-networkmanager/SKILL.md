---
name: wireguard-networkmanager
description: Imports and checks WireGuard VPN configs (.conf from Proton VPN, Mullvad, IVPN, AirVPN, Windscribe) in NetworkManager, so they work from the KDE Plasma network applet without the provider's client or a keyring. Covers choosing a server with IPv6, IPv6 and DNS leaks, the missing kill switch, and removal. Use when a WireGuard .conf appears, for a VPN on KDE without a GTK/Electron app, when the provider's app trips on the keyring, or on `nmcli connection import type wireguard` and "The name of the WireGuard config must be a valid interface name".
---

# WireGuard through NetworkManager (KDE)

Provider VPN apps on Linux target GNOME and break on KDE at the keyring:
`gnome-keyring` and `ksecretd` race for the same D-Bus name at boot. But
NetworkManager speaks WireGuard natively and plasma-nm has a UI for it, so an
imported `.conf` becomes an ordinary applet connection — no extra daemon, no
keyring, no provider app.

Scripts are in `scripts/` next to this file; run them from the skill folder.

## Before generating the config: IPv6 picks the server

```bash
ip -6 -brief address show scope global
```

A global address on a physical interface means the network has real IPv6.
Then the config must route `::/0` as well as `0.0.0.0/0`; otherwise IPv4 goes
through the tunnel, the IP test passes, and all IPv6 traffic (Google,
YouTube, anything behind Cloudflare) leaves with the real address.

With IPv6 on the network, a server the provider marks "IPv6" is a
requirement. Among those, pick load under ~80%, then the nearest country.
Before importing:

```bash
grep -i '^AllowedIPs' file.conf   # must contain 0.0.0.0/0, ::/0
```

## Import

```bash
scripts/wg-import.sh ~/Downloads/file.conf Proton
```

The script tightens the `.conf` to 600 (browsers save it 644, private key
inside), warns when the network has IPv6 and the config does not, shortens the
name to NetworkManager's limit, imports, turns autoconnect off, and renames the
connection for the applet.

The second argument is an optional **prefix**, usually the provider. The rest
of the name comes from the `.conf`: providers write the server label as the
first comment under `[Peer]` (`# US-FREE#63`), so `Proton` becomes
`Proton US-FREE#63`. Deriving the name keeps it stable across imports and
identical to the provider's dashboard, where load and the IPv6 tag are compared.

## Verify before trusting it

```bash
scripts/wg-check.sh
```

Checks the three leaks of this setup — IPv4, IPv6 and DNS — and exits 1 if
any escapes. Run it after importing and whenever the connection drops and
comes back. It checks that the tunnel exchanged packets (RX zero means no
handshake), that the public IPv6 differs from the LAN's, and that interfaces
with a default route no longer resolve DNS on their own.

## Traps

- **The file name becomes the interface name**: at most 15 characters, no
  special characters, or the import fails with "must be a valid interface
  name". The script imports from a short-named copy.
- **No `sudo`.** polkit already lets the active session create system
  connections, and `sudo` fails without a terminal.
- **Do not test the IP right after importing.** The handshake and DNS switch
  take seconds; an immediate check is a false negative. Wait and retry.
- **The default route is not where you look.** NM uses policy routing: the
  tunnel's default goes to its own table, so `ip route show default` still
  shows the Wi-Fi. Use `ip rule` and `ip route show table all default`, or test
  the public IP.
- **Where the private key ends up.** On Ubuntu with netplan, NM writes
  profiles to `/etc/netplan/90-NM-<uuid>.yaml` (root, 0600), and
  `/etc/NetworkManager/system-connections/` stays empty. Elsewhere it is the
  traditional path. Matters for backup and removal.

## Testing without taking anyone's internet

To exercise import, applet or leak detection without hijacking real traffic,
generate a fake config with `AllowedIPs = 192.0.2.0/24` (TEST-NET, routes
nowhere) and keys from `openssl rand -base64 32`. The tunnel comes up, shows in
the applet and runs the whole path without touching the default route.

## Daily use and limits

Toggle from the Plasma network icon, or `nmcli connection up "<name>"` /
`nmcli connection down "<name>"`. Several countries can coexist as separate
entries; keep one active (free plans usually allow one connection).

**There is no kill switch.** If the tunnel drops, traffic silently returns to
the normal route. That is why the script sets `autoconnect no`: the VPN exists
only when chosen, instead of coming up alone and implying protection it does
not give. Whoever needs a kill switch needs the provider's client (for example
`mullvad lockdown-mode on`).

Changing country means changing connection. Port forwarding, NetShield and
similar are chosen when generating the `.conf` on the provider's site; changing
them means generating another.

## Remove

```bash
nmcli connection delete "<name>"
```

The netplan YAML goes too, a moment later; an immediate check reports a
leftover that is not there. Look again before hunting for residue.
