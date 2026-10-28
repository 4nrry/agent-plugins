# mobile-agent

What fails silently when an agent works on a mobile app: the device layer
(adb, emulator, UI dumps, mirroring a phone) and the bundler layer (Expo,
Metro, prebuild). It does not teach the `android` CLI or SDK — Google's own
catalog does (`android skills list`).

```
/plugin install mobile-agent@4nrry
```

| Component | Path | Does |
|---|---|---|
| Skill | `skills/android-device/` | UI dumps, GL surfaces, screenshots, input, tunnels, other sessions' processes; bundles `adb-ui.sh`, `adb_ui.py` and `verify_tool_facts.py` |
| Skill | `skills/expo-metro/` | Silent prebuild, Metro per worktree and port, missing `node_modules` (hardlinks, not symlinks), native modules, `EXPO_PUBLIC_`, SDK in non-interactive shells |
| Skill | `skills/android-mirror/` | scrcpy over wireless debugging without a second adb |
| Skill | `skills/maestro/` | Writing and running Maestro flows: selectors, env defaults, `clearState`, dev client, debug artifacts |
| Skill | `skills/preflight/` | `/mobile-agent:preflight`: what is already running, and which checkout owns it |
| Hooks | `hooks/` | Twelve narrow `PreToolUse` guards, one permission rule each; they warn and never block |
| MCP | `.mcp.json` | Maestro's own server (`maestro mcp`): list devices, read the screen, run inline YAML or saved flows |

## Maestro MCP

The server ships inside the Maestro CLI, which the plugin does not install:
`maestro` must be on the `PATH` the agent starts with (the installer puts it
in `~/.maestro/bin`), with Java 17 or newer. The server runs wherever the
plugin is enabled, so install the plugin in the app's own repository
(`--scope local` or `project`), not for every project. Flows the agent
writes belong in the app repository, under `.maestro/`.

## Guards

| `if` | Warns about |
|---|---|
| `Bash(adb kill-server)` | drops every session's tunnels; looks like the backend is down |
| `Bash(apt install *)`, `Bash(apt-get install *)`, with and without `sudo` | distro `scrcpy` pulls an `adb` that shadows the SDK's |
| `Bash(scrcpy *)`, `Bash(scrcpy)` | without `ADB=`, scrcpy may use another adb and drop tunnels |
| `Bash(pkill *)`, `Bash(pgrep *)` | `-f` matches your own command line |
| `Bash(adb shell uiautomator *)` | a dump to a file can serve the previous tree |
| `Bash(npx expo run:*)`, `Bash(expo run:*)` | no prebuild when `android/` exists; empty `ANDROID_HOME` |

Each handler holds one rule because `if` has no combinators; all exit 0.

**Evidence:** behavior checks, not effect measurements —
[`bench/plugins/mobile-agent/results/2026-10-09-verification-CLAIMS.md`](../../bench/plugins/mobile-agent/results/2026-10-09-verification-CLAIMS.md).
