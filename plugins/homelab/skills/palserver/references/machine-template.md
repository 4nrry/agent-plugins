# Machine file template

## Contents
- Why outside the repository
- The template: machine, install, active config, network, measured usage,
  restart history, restart timer, moving the server, second server

Machine-specific values — addresses, versions, measured numbers — live in
`~/.claude/palserver.local.md`, never in the plugin. Copy this template there
from the skill folder, fill it in, and never commit the result:

```bash
cp references/machine-template.md ~/.claude/palserver.local.md
```

It stays outside the repository because it holds VPN, LAN and router IPs (a
public commit cannot be taken back), and `.gitignore` is no fix: an ignored
file exists only on the author's machine, so the skill would ship pointing at
nothing.

---

# Palworld — machine `<HOSTNAME>`

Measured on `<YYYY-MM-DD>`. Re-measure after a hardware change or a large
patch; an old number is worse than none because it looks current.

## Machine

`<CPU>`, `<RAM>` GB, `<DISTRO AND VERSION>`, `<DE/WM>`.

## Install

| Item | Value |
|---|---|
| Steam | `<apt / flatpak / ...>` |
| steamcmd | `<path, or "not installed">` |
| PalServer | via `<Steam client / steamcmd>`, AppID 2394010 |
| Prefix | `<~/.local/share/Steam/... or ~/Steam/...>` |
| Version | `v<X.Y.Z.NNNNNN>`, buildid `<NNNNNNNN>`, updated `<YYYY-MM-DD>` |
| Size | `<N>` GB |
| Active world | `SaveGames/0/<HEX>/` |
| Manual backups | `<path>` |

## Active config

Only the keys changed, not the whole ini:

```
DeathPenalty=<...>
AutoSaveSpan=<...>
bIsUseBackupSaveData=<True|False>
RESTAPIEnabled=<True|False>
RESTAPIPort=<...>
AdminPassword=<"" if empty>
PublicPort=<...>
```

Write down explicitly when `AdminPassword` is empty: no admin command works.

## Network

| Item | Value |
|---|---|
| Mesh VPN | `<100.x.y.z>` (`<host>.<tailnet>.ts.net`) |
| LAN | `<192.168.N.M>` (`<interface>`) |
| Router | `<192.168.N.1>` |
| Public IP | `<static / dynamic>` |

How players join and why: `<mesh VPN / port forward / community server>`. For
a port forward, also record the DHCP reservation and DDNS. Record
`tailscale netcheck` (`UDP: true`, `MappingVariesByDestIP: false` mean direct
connections work) and whether there is CGNAT.

Local firewall: `<ufw/nftables? what it allows>`.

## Measured usage

| Uptime | RSS | CPU | Players online | Date |
|---|---|---|---|---|
| at start | `<N>` GB | `<N>`% | `<N>` | `<YYYY-MM-DD>` |
| `<N>`h | `<N>` GB | `<N>`% | `<N>` | `<YYYY-MM-DD>` |

The players and date columns are the point: uptime alone explains nothing.
Separate commanded restarts (config, update) from crashes, check
`journalctl --user -u palworld | grep -c 'Game version is'` before reading a
curve, and when two readings disagree, keep both with their dates.

## Restart history

Boots, crashes, and whether `Restart=on-failure` covered them all:

```bash
journalctl --user -u palworld | grep -E 'Signal 11 caught|Game version is'
```

## Restart timer

The chosen hour and where it came from (this machine's boot history, not a
default). `Persistent=false`.

## Moving the server

Machines already ruled out, and why.

## Second server

Ports already taken here. `RESTAPIPort` (8212) and `RCONPort` (25575) are
reserved in the ini even when off.
