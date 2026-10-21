# homelab

Software you maintain yourself on a Linux box, where the official docs stop.
Each skill covers failures that raise no error.

```
/plugin install homelab@4nrry
```

| Component | Path | Does |
|---|---|---|
| Skill | `skills/palserver/` | Palworld dedicated server: install, systemd, editing the ini without losing the edit, REST API admin, player access, backups, updates, a second server, guilds |
| Skill | `skills/wireguard-networkmanager/` | Import a provider's WireGuard `.conf` into NetworkManager for the Plasma applet, without the provider's client or a keyring; bundles `wg-import.sh` and `wg-check.sh` |
| Skill | `skills/tarball-installer/` | One layout for app tarballs: versioned directory, `current` symlink, wrapper on PATH, validated `.desktop`, hicolor icon; bundles `tarball-install` |

## Traps

| Trap | What happens |
|---|---|
| Config erased on shutdown | PalServer rewrites its ini on exit, so `systemctl restart` never applies an edit. Stop, edit, start. |
| `kill` that resurrects | SIGINT exits 130 and `Restart=on-failure` brings it back; only `systemctl stop` stops it. |
| Updating a running server | Steam swaps the binary under the process, which crashes. |
| Guilds have no server side | No admin command or REST route touches guild roles. |
| VPN that passes the IP test and leaks | `AllowedIPs = 0.0.0.0/0` without `::/0` sends all IPv6 out with the real address. |
| No kill switch | If the tunnel drops, traffic silently takes the normal route; imports stay `autoconnect no`. |
| Self-updater in `/opt` | Apps that update themselves cannot write to a root-owned install directory. |
| Large-only icon | The menu falls back to another app's icon when names share a prefix. |

## Machine state stays out

No IP, installed version or measured number lives in this repository.
`palserver` reads `~/.claude/palserver.local.md` if it exists; the published
part is its template, `skills/palserver/references/machine-template.md`. A
`.gitignore`d file would exist only on the author's machine and ship as a dead
reference.

**Evidence:** behavior observed on one installation, not run records —
[`bench/plugins/homelab/results/2026-09-07-palserver-wireguard-CLAIMS.md`](../../bench/plugins/homelab/results/2026-09-07-palserver-wireguard-CLAIMS.md).
