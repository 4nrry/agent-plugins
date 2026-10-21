---
name: palserver
description: Operates a self-hosted Palworld dedicated server (PalServer) on Linux — steamcmd install, systemd start and stop, editing PalWorldSettings.ini without the server erasing the edit, admin commands over the REST API, player access, backups, updating after a patch, a second server, and guild or Guild Master problems. Use when the task mentions Palworld, PalServer, PalWorldSettings.ini, DeathPenalty, palworld.service, AppID 2394010, or "my Palworld server".
---

# Palworld dedicated server on Linux

Machine-specific state — addresses, installed version, measured numbers —
lives in `~/.claude/palserver.local.md`, outside the plugin. **If it exists,
read it before answering anything about "my server"**; it wins wherever it and
this skill disagree. Its template is
[references/machine-template.md](references/machine-template.md).

The official docs are incomplete (they do not list every ini key). When they
and the installation disagree, the files on disk win.

## Paths

The prefix depends on how it was installed; call it `$PALSERVER`:

| Installed by | Prefix |
|---|---|
| steamcmd (official) | `~/Steam/steamapps/common/PalServer` |
| Steam client | `~/.local/share/Steam/steamapps/common/PalServer` |

| What | Where, under `$PALSERVER` |
|---|---|
| Active config | `Pal/Saved/Config/LinuxServer/PalWorldSettings.ini` |
| Sample only — editing it does nothing | `DefaultPalWorldSettings.ini` |
| Which world loads | `Pal/Saved/Config/LinuxServer/GameUserSettings.ini`, `DedicatedServerName=` |
| Worlds | `Pal/Saved/SaveGames/0/<HEX>/` |
| Built-in backups | `Pal/Saved/SaveGames/0/<HEX>/backup/world/<timestamp>/` |
| Game logs | `Pal/Saved/Logs/` |

`Pal/Saved/` appears only after the first boot; before it there is no ini to edit.

Install, systemd unit and updates: [references/install.md](references/install.md).

## Start and stop

With a user unit named `palworld`:

```bash
systemctl --user status palworld
systemctl --user start palworld    # or stop
journalctl --user -u palworld -f
```

A user unit needs `loginctl enable-linger $USER` to start at boot without a
login. For a system unit, use `sudo systemctl` and drop `--user`.

**Never stop it with `kill`.** SIGINT makes the server exit 130, which
`Restart=on-failure` reads as a crash and restarts. `systemctl stop` is a
commanded stop and is not restarted.

## Editing the config: stop, edit, start

The server **rewrites** `PalWorldSettings.ini` on shutdown with what it loaded
into memory. So `systemctl restart` never applies an edit: the stop overwrites
the file before the start reads it. The only working order:

```bash
systemctl --user stop palworld
# edit PalWorldSettings.ini now, with the server stopped
systemctl --user start palworld
wc -c "$PALSERVER/Pal/Saved/Config/LinuxServer/PalWorldSettings.ini"
```

A few thousand bytes means the config loaded; **1 byte means it was ignored**.
Do not compare against an exact size: the server drops comment lines when it
rewrites the file.

A restart with no pending edit is safe: the stop writes what was in memory and
the start reads it back.

Format, the single-line trap, PvP and common keys:
[references/configuration.md](references/configuration.md).

## Admin commands

A headless server has no console. Use the **REST API**, or a player who
authenticated with `AdminPassword` in the in-game chat. With `AdminPassword`
empty, no admin command works by either route. **RCON is deprecated** and
scheduled to stop working; build nothing new on it.

Routes, auth, the 13 commands and the security warning:
[references/admin-api.md](references/admin-api.md).

## Player access

Ports: **8211/UDP** (game, required, changed with `-port=`) and **27015/UDP**
(Steam query, optional, **not configurable**). Never TCP.

| Model | How players join | Consoles |
|---|---|---|
| Dedicated (default) | **Join Multiplayer Game (Dedicated Server)**, field under the list, `IP:port` | Xbox and PS5 **cannot** |
| Community (`-publiclobby`) | `Community server` tab, by name | The only way for Xbox and PS5 |

If any player is on a console, a community server is required.

To avoid opening the router, use a mesh VPN (Tailscale, Netbird, ZeroTier):
players connect to the VPN IP on 8211. With a port forward of 8211/UDP
instead, set `ServerPassword`. Details: [references/hardware-network.md](references/hardware-network.md).

## Backups

The only official mechanism is `bIsUseBackupSaveData=True`, which keeps
rotating copies (every 30 s ×5, 10 min ×6, 1 h ×12, 1 day ×7) in `backup/`
**inside the same world tree, on the same disk** — not a backup. Copy out:

```bash
tar czf ~/palworld-backup/save-$(date +%Y%m%d-%H%M%S).tar.gz \
  -C "$PALSERVER/Pal/Saved" SaveGames
```

Force a save first with the REST `save` route or `/Save`. Restore only with
the server stopped.

## Restart on symptoms, not on a clock

Uptime alone does not predict memory use; load (players online, spawn
density, raids) explains more. The official docs do not recommend periodic
restarts, and a scheduled one kicks whoever is playing. Restart when:

1. Players report rubber-banding or lag while Pals work.
2. RSS or CPU exceeds anything already measured on this installation (no
   universal threshold; take it from your own series, see
   [references/hardware-network.md](references/hardware-network.md)).
3. `Level.sav` stops changing every `AutoSaveSpan` seconds with players online.

`Signal 11` in the journal is not a reason: `Restart=on-failure` covers it.

If a timer is wanted anyway, pick a low-traffic hour and do not set
`Persistent=true` on a user timer — it fires right after boot and kills a
server that just came up.

## Do not

- Add `-useperfthreads -NoAsyncLoadingThread -UseMultithreadForDS`: early-access
  folklore; the official docs say v1.0+ may run better without them.
- Edit `DefaultPalWorldSettings.ini` expecting an effect.
- Split the `OptionSettings=` line.
- Expose the REST API to the internet.
- Plan on mods: officially they work only on Windows dedicated servers.
- Host on weak hardware: officially 4 cores, 16 GB (8 GB "bootable"), SSD.

## More worlds, or a second server

Several worlds can share `SaveGames/0/`; switch which loads by editing
`DedicatedServerName=` in `GameUserSettings.ini` with the server stopped.

Two servers **at once** need a second installation in another folder; two
instances on one tree fight over the same config and world. In the copied
unit change `Description`, `WorkingDirectory` and `ExecStart` (add
`-port=8213`; `PalServer.sh` passes `"$@"` through). Avoid 8212 and 25575,
which the ini reserves for `RESTAPIPort` and `RCONPort`. Do not plan a second
query port: there is no `-queryport`, and it only matters for community
listing. Each instance costs a full server's RAM and CPU. The official docs do
not cover multiple instances; this procedure is derived.

## Guilds and Guild Master

Roles: Guild Master, Sub Master, Member, Guest. **Nothing server-side manages
guilds**: none of the 13 admin commands nor the REST API touches them, and
`AdminPassword` does not reach guild roles.

Transferring master is in-game only: guild menu, select the member, **MAKE
GUILD MASTER**, done by the current master. Nobody changes their own role or
demotes the master, and the master cannot leave without transferring first. If
master was handed over by mistake, only the new master can give it back.

`AutoTransferMasterThresholdDays` and `AutoTransferMasterCheckIntervalSeconds`
exist in the ini but are undocumented, and their behavior is unverified. Do not
promise the role comes back on its own.

Last resort if the master is gone for good: edit `Level.sav` with
`palworld-save-tools` and reassign the master — server stopped, backup first.
