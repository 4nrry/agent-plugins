# PalWorldSettings.ini

## Contents
- Format
- Safe edit
- DeathPenalty
- Common keys
- PvP
- Keys added in 1.0
- Sources

## Format

Every option lives on **one line**:

```ini
[/Script/Pal.PalGameWorldSettings]
OptionSettings=(Difficulty=None,DayTimeSpeedRate=1.000000,...,bAllowEnemyCampSpawnNearBaseCamp=False)
```

Splitting that line makes the server ignore the whole file and fall back to
defaults, with no error — the most common cause of "I edited it and nothing
changed".

## Safe edit

1. `systemctl --user stop palworld`
2. Start from `DefaultPalWorldSettings.ini` if the active file is empty; never
   edit the Default itself.
3. Change only what is needed, with a unique-match replace that fails loudly.
4. `systemctl --user start palworld`
5. `wc -c` the file: 1 byte means it was ignored.

The server drops `;` comment lines when it rewrites the file; that is normal.

## DeathPenalty

| Value | Dropped on death |
|---|---|
| `None` | Nothing |
| `Item` | Backpack items; equipment and Pals stay |
| `ItemAndEquipment` | Items and equipment; Pals stay |
| `All` | Everything, including the **active party** Pals (not the Palbox) |

Drops become a chest at the death spot that the owner can recover.
`bCanPickupOtherGuildDeathPenaltyDrop=False` (default) stops other guilds from
looting it. Web guides disagree on the default; read the local Default file.

## Common keys

```
ExpRate=1.000000
PalCaptureRate=1.000000
CollectionDropRate=1.000000        # ore, wood, stone
EnemyDropItemRate=1.000000
WorkSpeedRate=1.000000             # base Pals; exists though undocumented
PalEggDefaultHatchingTime=1.000000 # 0 = hatches instantly
DayTimeSpeedRate=1.000000
bEnablePlayerToPlayerDamage=False  # not enough for PvP on its own
bEnableFriendlyFire=False
ServerName="Default Palworld Server"
ServerPassword=""                  # join password
AdminPassword=""                   # empty = no admin command works
GuildPlayerMaxNum=20
BaseCampWorkerMaxNum=15
AutoSaveSpan=30.000000             # seconds
bEnableInvaderEnemy=True           # hosts report off saves RAM; unverified
```

For a small group of friends, hosting blogs (not official) converge on
`ExpRate=2.0`, `PalCaptureRate=1.5`–`2.0`, `CollectionDropRate=2.0`,
`DeathPenalty=None` or `Item`: multiplayer cannot be paused, so a punishing
death costs the whole group's evening.

## PvP

The official docs require **three keys together**:

```
bIsPvP=True
bEnablePlayerToPlayerDamage=True
bEnableDefenseOtherGuildPlayer=True
```

Only `bEnablePlayerToPlayerDamage` is the usual mistake. The docs call PvP a
trial feature "not covered by support"; it also disables missions, adjusts
some weapons and increases the minimum distance between bases.

## Keys added in 1.0

No classic key was removed or renamed; early-access guides still hold for
what they cover.

| Area | Keys |
|---|---|
| Hardcore | `bHardcore`, `bPalLost`, `bCharacterRecreateInHardcore` |
| Voice chat | `bEnableVoiceChat`, `VoiceChatMaxVolumeDistance`, `VoiceChatZeroVolumeDistance` |
| Crossplay | `CrossplayPlatforms=(Steam,Xbox,PS5,Mac)` |
| Respawn | `RespawnPenaltyDurationThreshold`, `RespawnPenaltyTimeScale`, `BlockRespawnTime` |
| Inactive guild | `AutoTransferMasterThresholdDays`, `AutoTransferMasterCheckIntervalSeconds` |
| Progression | `bAllowEnhanceStat_*` (5), `DenyTechnologyList` (ids on the docs' `technologyids` page) |
| Automation | `RESTAPIEnabled`, `RESTAPIPort`, `BanListURL` |
| Performance | `MaxGuildsPerFrame`, `ServerReplicatePawnCullDistance`, `PhysicsActiveDropItemMaxNum` |

`RespawnPenaltyTimeScale` multiplies the cooldown when a player dies again
within `RespawnPenaltyDurationThreshold` seconds.

## Sources

Most "best settings" guides are hosting-company blogs and contradict each
other; the official docs omit keys that exist (`WorkSpeedRate`). The local ini
wins. The values chosen on a specific machine, and why, belong in
`~/.claude/palserver.local.md` ([machine-template.md](machine-template.md)).
