# Batch 2026-09-07-palserver-wireguard — claims

**Notes, not run records.** Imported from the homelab README and skills
(0.1.0–0.2.3): behavior observed on one real installation over about two
weeks around 2026-09-07, plus checks against the official docs and the server
binary. No record conforms to `bench/schema/run.schema.json`. These notes
support "this behaves as described"; they support no claim that the plugin
improves an agent's outcomes, which would need paired arms.

**PalServer memory, and a retracted claim.** 0.1.0 said RSS grows with uptime,
never stabilizes, and that a daily timer restart fixes it. The series does not
support that, nor the opposite; variables were never isolated:

| uptime | RSS | context |
|---|---|---|
| 2h | 2.13 GB | players online |
| 4h | 1.47 GB (peak 1.80) | earlier session |
| 6h10 | 2.40 GB | right after doubling spawn density |
| 14h | 2.20 GB | players online |
| 20h | 1.73 GB | earlier session |
| 11h39 | **0.59 GB** | idle |

Observed range 0.6–2.4 GB RSS, 0.4–2.1 cores. The longest reading is the
lightest; load explains more than time. The skill now restarts on symptoms.

**PalServer operations**
- Journal over the period: 14 boots, 4 `Signal 11` crashes, all recovered by
  `Restart=on-failure`.
- 2026-09-07: a Steam update with the server running swapped the binary under
  the process, which died with `Signal 11`; the world reached disk through
  autosave, not a graceful shutdown.
- A second instance was estimated at about 2 GB RSS and ~1.3 cores after a few
  hours, from the single-server readings above.
- Machine verdicts used in 0.2.x (derived, not official): 16 GB + modern CPU +
  SSD fine; 8 GB + decent CPU + SSD for few players; 8 GB with an old
  dual-core rubber-bands with Pals at base; 4 GB insufficient.
- Config reference was v1.0.3.101283, 120 keys; its factory
  `DefaultPalWorldSettings.ini` had `DeathPenalty=Item`, against web guides
  claiming `All`.
- Binary checks: no `queryport` string and no `27015` literal (the query port
  is Steam's); the reason `AutoTransfer` and the strings
  `FailedCannotChangeOwnRole` and `FailedCannotDemoteMaster` are present.
  `AutoTransferMasterThresholdDays` behavior was not exercised.
- The steamcmd update was not run against a Steam-client install.

**WireGuard through NetworkManager**
- `Book4Ultra-US-FREE-122.conf` was rejected with "The name of the WireGuard
  config must be a valid interface name followed by '.conf'".
- `pkcheck --action-id org.freedesktop.NetworkManager.settings.modify.system`
  answered `yes` for the active session, so no `sudo` was needed.
- On Ubuntu 23.10+ NetworkManager wrote profiles to
  `/etc/netplan/90-NM-<uuid>.yaml`; `/etc/NetworkManager/system-connections/`
  was empty. NetworkManager has supported WireGuard natively since 1.16.
- `wg-import.sh` once exited 1 after a successful import: an EXIT trap ending
  in a false `&&` under `set -e`. Fixed with `return 0`.

**Not established:** whether a periodic restart is ever needed, and after how
many hours; how the skills change an agent's behavior.
