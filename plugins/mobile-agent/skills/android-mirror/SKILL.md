---
name: android-mirror
description: Mirrors and controls a physical Android device's screen on a Linux PC with scrcpy over the wireless debugging already connected, without installing a second adb that drops the tunnels. Covers what does not work (KDE Connect, Phone Link, DeX for Linux), installing without shadowing the SDK's adb, proving it works without a window, and Wayland, hybrid-GPU and secure-screen traps. Use when you need to see a real phone without holding it, record a test on video, or when the mirror "won't connect" and adb drops with it.
---

# Mirroring an Android device

Use **scrcpy** (<https://github.com/Genymobile/scrcpy>): it mirrors, takes
mouse and keyboard, records, and talks to the device through adb. What goes
wrong is not the mirror but a second `adb` installed with it.

Not alternatives: KDE Connect does not mirror the screen; Phone Link is
Windows-only; Samsung DeX for Linux is discontinued; Android Studio's Running
Devices mirrors inside the IDE only.

## Install without a second adb

The distro `scrcpy` package depends on the distro `adb`, which lands in
`/usr/bin` ahead of the SDK's `platform-tools`. Two adb versions restart the
server on every call (`adb server version doesn't match this client`),
dropping every `adb reverse` tunnel and the wireless connection.

Use the official release tarball per user, with a wrapper that pins the SDK's
adb through the `ADB` variable scrcpy reads:

```bash
gh release download --repo Genymobile/scrcpy --pattern 'scrcpy-linux-x86_64-*.tar.gz'
tar -tzf scrcpy-linux-x86_64-*.tar.gz | head          # look before extracting
```

Extract to `~/.local/opt/scrcpy/<version>/` with `current` pointing at it (the
homelab plugin's `tarball-install` does this), then `~/.local/bin/scrcpy`:

```sh
#!/bin/sh
export ADB="${ADB:-${ANDROID_HOME:-$HOME/Android/Sdk}/platform-tools/adb}"
exec "$HOME/.local/opt/scrcpy/current/scrcpy" "$@"
```

The release publishes no checksum; the official repository over TLS is the
only check. Say so rather than claiming verification.

## Connect

If the device is in `adb devices`, scrcpy finds it (`-s <serial>` for more
than one). For wireless debugging, connect by mDNS name, not `IP:port`:
`adb connect adb-<serial>-xxxx._adb-tls-connect._tcp`. Never `adb kill-server`
to fix a drop — it causes the drop.

## Prove it without a window

```bash
timeout 12 scrcpy -s <serial> --no-playback --no-audio --record proof.mkv
ls -la proof.mkv                  # did it grow?
adb devices; adb reverse --list   # connection and tunnels still there?
```

The file lacks a trailer when `timeout` kills scrcpy: proof, not a recording.

## Use

```bash
scrcpy --window-title "phone · app"     # mouse taps, keyboard types
scrcpy --record ~/Videos/test.mkv
scrcpy --stay-awake                     # only works over USB
```

Check flags against the installed binary (`scrcpy --help`) before citing them.

## Traps

- **Wayland:** runs under XWayland by default. On Plasma, KWin may block
  compositing while the window is open; `SDL_VIDEODRIVER=wayland` tries the
  native backend.
- **Black window on hybrid GPUs:** hardware decoding is the default;
  `--hwdec=disabled`.
- **Black only on some screens:** `FLAG_SECURE` content (banking, vaults, some
  logins) never mirrors. No fix without root.
- **Mouse does not tap (Samsung, Xiaomi):** enable "USB debugging (Security
  settings)" in developer options and reboot.
- **FFmpeg "profile 100" warnings** are informational.
