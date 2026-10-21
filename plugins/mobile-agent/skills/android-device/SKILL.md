---
name: android-device
description: Covers what fails silently when an agent drives an Android device or emulator — UI dumps that serve stale state, GL surfaces invisible to accessibility, screenshots that exhaust session memory, adb tunnels that drop on their own, and processes that belong to someone else. Use before automating any on-device flow, and again when a screen seems stuck with no error. For the `android` CLI itself, use `android skills add` and `android docs search`, which Google maintains.
---

# Android device

Failures here rarely raise an error: they return stale data or nothing, and
you debug the wrong thing. The `android` CLI's own catalog (`android skills
list`, `android docs search "<term>"`) covers the CLI, AGP, Compose and the
SDK better than this file; this file covers the silent failures.

## Before starting anything, see what is already up

Ports, emulator locks and the adb server are one per machine, and starting a
second one breaks someone else's session. Run the `preflight` skill, or:

```bash
adb devices; adb reverse --list; ss -ltnp | grep -E ':(8081|8082)'
readlink /proc/<pid>/cwd          # which checkout owns a process
```

## Reading the screen

Use the accessibility tree, read from stdout — a dump to a file can fail
silently and leave the previous one in place:

```bash
adb exec-out uiautomator dump /dev/tty
```

GL surfaces (maps, video, WebView, canvas) do not appear in the tree; an empty
or shallow dump there does not mean the app is stuck. Use the visual path:

```bash
android screen capture --annotate -o shot.png
adb shell input $(android screen resolve --screenshot shot.png --string "tap #34")
```

The flag is `--screenshot`; Google's own skill text says `--screen`, which the
binary rejects. Bundled helpers, from this skill's directory:

```bash
scripts/adb-ui.sh dump              # labels and bounds from stdout; explains an empty tree
scripts/adb-ui.sh tap "Continue"    # taps the smallest clickable node that matches
scripts/adb-ui.sh shot out.jpg      # screenshot already downscaled, safe to read
scripts/verify_tool_facts.py        # checks the CLI flags cited here against the installed binary
```

## Screenshots

A full screenshot is several MB; reading it raw can kill the agent session.
Downscale first: `vipsthumbnail shot.png --size 640x -o small.jpg[Q=85]`.
`screencap` takes about a second (record with `screenrecord` for fast
transitions) and sometimes returns white before a repaint; a micro-swipe fixes
it.

## Input

- Leave about 0.3 s between `input` events; a tight loop triggers "Not
  Responding".
- Check what `input text` does in your app first: in a dev client some
  characters trigger developer shortcuts and reload the bundle. Type in
  chunks around them.

## Wireless debugging

Connect by mDNS service name, not `IP:port` — the name works where the
address listed by mDNS can fail:

```bash
adb mdns services
adb connect adb-<serial>-xxxx._adb-tls-connect._tcp
```

## Tunnels drop

`adb kill-server` (or a client/server version mismatch) drops every session's
`adb reverse` tunnels, and the app shows a network error as if the backend
were down. Check `adb reverse --list` and re-apply before debugging the
backend. Never run `adb kill-server` as a retry reflex.

## Processes that are not yours

- Do not kill an emulator, bundler, container or dev server you did not start;
  ask.
- Never `pkill -f`/`pgrep -f` with a pattern that appears in your own command
  line: it matches your shell. Use `-x` with the exact name, or a PID.
- Stop the emulator with `adb emu kill`, not SIGTERM, which leaves the AVD
  lock behind.

## Emulator limits

The emulator has no Bluetooth hardware: a scan returns nothing and raises no
error. Real-radio behavior needs a physical device.

## The `android` bootstrapper

`cmdline-tools/latest/bin/android` downloads and installs the real CLI (hundreds
of MB) on any invocation, `--version` included. It is not a read-only command.
