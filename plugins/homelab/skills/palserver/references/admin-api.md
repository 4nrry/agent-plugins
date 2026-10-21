# Admin commands, REST API and RCON

A headless server has no console. Use the REST API; the in-game chat needs
someone logged in, and RCON is deprecated.

## The 13 commands

| Command | Does |
|---|---|
| `/AdminPassword` | Gain admin privileges |
| `/Shutdown` | Shut down, optional delay |
| `/DoExit` | Force stop |
| `/Broadcast` | Message everyone |
| `/KickPlayer` | Kick |
| `/BanPlayer` | Ban |
| `/UnBanPlayer` | Unban |
| `/TeleportToPlayer` | Go to a player |
| `/TeleportToMe` | Bring a player |
| `/ShowPlayers` | List connected players |
| `/Info` | Server info |
| `/Save` | Save the world |
| `/ToggleSpectate` | Spectator mode |

None touches guilds. In chat, `/AdminPassword <password>` unlocks the rest;
it requires `AdminPassword` set in the ini.

## REST API

Enable in `PalWorldSettings.ini`, with the server stopped:

```
RESTAPIEnabled=True
RESTAPIPort=8212
AdminPassword="some-password"
```

Auth is HTTP Basic with `AdminPassword` as the password. The username is not
in the static docs; `admin` is the convention, unconfirmed. Check with a
harmless route — 401 means the wrong user:

```bash
curl -su admin:"$ADMIN_PASSWORD" http://127.0.0.1:8212/v1/api/info
```

Routes under `/v1/api/`:

| Route | Method | Does |
|---|---|---|
| `info` | GET | Version and server name |
| `players` | GET | Player list |
| `settings` | GET | Active config |
| `metrics` | GET | FPS, uptime, players, memory |
| `announce` | POST | Message everyone, body `{"message": "..."}` |
| `kick` | POST | Kick |
| `ban` | POST | Ban |
| `unban` | POST | Unban |
| `save` | POST | Save the world |
| `shutdown` | POST | Shut down |
| `stop` | POST | Force stop |
| `game-data` | GET | Snapshot of world actors; needs `-enable-gamedata-api` |

The docs warn the API is "not designed to be exposed directly to the
Internet". Keep it on `127.0.0.1`, the LAN or the VPN; never port-forward it.

Typical uses: `save` before a hot backup, `announce` before a restart,
`metrics` to watch memory without `ps`.

## RCON

Deprecated and scheduled to stop working. The ini still has `RCONEnabled` and
`RCONPort` (default 25575) and generic clients still connect; migrate any RCON
script to the REST API. Port 25575 stays reserved in the ini even with RCON off.
