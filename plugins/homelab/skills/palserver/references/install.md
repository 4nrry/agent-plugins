# Install, systemd unit and updates

## Contents
- Install with steamcmd
- Installed by the Steam client
- systemd unit
- Launch arguments
- Update after a patch

## Install with steamcmd

The official docs cover steamcmd only:

```bash
steamcmd +login anonymous +app_update 2394010 validate +quit
cd ~/Steam/steamapps/common/PalServer
./PalServer.sh
```

AppID 2394010 is the dedicated server; `anonymous` needs no account or game
license. The same command installs and updates; `validate` checks integrity.
The install directory depends on steamcmd's configuration.

Official requirements: 4+ cores, 16 GB recommended ("8GB is also bootable"),
SSD ("Low-performance storage may corrupt saved data"), 64-bit Windows or Linux.

The first boot creates `Pal/Saved/`; before it there is no ini to edit.

## Installed by the Steam client

The server also installs from the Steam library, into
`~/.local/share/Steam/steamapps/common/PalServer`. It runs the same, but the
Steam client owns the folder through `appmanifest_2394010.acf`. **Do not point
steamcmd at that tree**: the two tools fight over the manifest. Pick one owner.

```bash
grep -E '"(buildid|LastUpdated|StateFlags)"' \
  ~/.local/share/Steam/steamapps/appmanifest_2394010.acf
```

`StateFlags 4` means installed and intact.

## systemd unit

The docs ship no unit. Adjust the paths:

```ini
[Unit]
Description=Palworld Dedicated Server
Documentation=https://docs.palworldgame.com/
After=network-online.target
Wants=network-online.target
StartLimitIntervalSec=300
StartLimitBurst=3

[Service]
Type=simple
WorkingDirectory=%h/Steam/steamapps/common/PalServer
ExecStart=%h/Steam/steamapps/common/PalServer/PalServer.sh

# SIGINT lets Unreal save the world before exiting.
KillSignal=SIGINT
KillMode=control-group
TimeoutStopSec=120

# Restart on a crash, but give up after 3 failures in 5 min (port taken).
Restart=on-failure
RestartSec=15

[Install]
WantedBy=default.target
```

- `KillSignal=SIGINT`: Unreal saves on SIGINT; the default SIGTERM is less graceful.
- `TimeoutStopSec=120`: saving a large world takes time; a short timeout
  becomes SIGKILL mid-save.
- `Restart=on-failure`: the server crashes now and then (`Signal 11 caught.`)
  and comes back.
- `StartLimitBurst=3` in 300 s: no endless loop when 8211 is already taken.

SIGINT exits 130, so a manual `kill -INT` triggers `Restart=on-failure`;
`systemctl stop` does not.

## Launch arguments

`PalServer.sh` passes `"$@"` to the binary, so these go in `ExecStart`:

| Argument | For |
|---|---|
| `-port=8211` | Game port |
| `-players=32` | Max players |
| `-publiclobby` | Community server (needed for Xbox and PS5) |
| `-publicip=` / `-publicport=` | When the server does not detect them |
| `-logformat=text` | `text` or `json` |
| `-enable-gamedata-api` | Enables the REST `game-data` route |
| `-NumberOfWorkerThreadsServer=X` | Worker threads |

## Update after a patch

Steam updates players' clients on its own; the server stays behind and
players get a version error. Check what is running:

```bash
journalctl --user -u palworld | grep 'Game version is' | tail -1
```

The manifest says what is **on disk**, the journal what is **in memory**; if
they differ, the server runs an old binary.

1. Warn players (REST `announce`).
2. `systemctl --user stop palworld`. Updating under a running server swaps the
   binary under the process, which then dies with `Signal 11`.
3. Back up the save.
4. Update: steamcmd installs with the `app_update` command above; Steam-client
   installs through the client, to avoid a manifest fight.
5. Check `PalWorldSettings.ini` survived: `wc -c`, 1 byte means ignored.
6. Start, and check the new version in the journal.

The steamcmd command has not been run against a Steam-client install, which
is exactly where it could fight the manifest.
