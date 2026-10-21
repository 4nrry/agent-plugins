# Batch 2026-10-09-verification — claims

**Notes, not run records.** Imported from the plugin's README (0.1.0–0.2.0).
No record conforms to `bench/schema/run.schema.json`. These notes support
"this behaves as described"; they support no claim that the plugin improves
an agent's outcomes. How often the guards fire in real use, and whether a
warning changed what came next, is not measured.

**Claim audit.** 37 statements in the skills checked against official Expo,
Metro, React Native, Android and Claude Code docs: 0 refuted, 9 true but
undocumented (marked "observed" at the time).

**Google's `android` skill catalog** (2026-08-31): 22 skills; one
(`android-profiler`) applies to an Expo/React Native project. The rest assume
Compose, XML views, Espresso, Kotlin or R8.

**Guards.** Exercised with simulated stdin: 17 match/no-match cases in 0.1.0,
19 more in 0.2.0 (apt, scrcpy, SDK note on `expo run`), in a fake environment
(stub SDK, scrcpy and adb in a temp dir).

**Device and bundler checks**

- Headless scrcpy proof against a Galaxy S20 (Android 13, Wi-Fi): 12 s of
  `--no-playback --record` produced 10 MB, `adb reverse --list` intact after.
- `apt-get install -s scrcpy` on Ubuntu 26.04 (2026-10-09) pulled scrcpy 3.3.4
  and the `adb` 34.0.5 package into `/usr/bin` — the premise of the apt guard.
  scrcpy flags were checked against 5.0.1 (2026-10-08), whose tarball ships
  adb 37.0.1.
- `expo-modules-autolinking resolve` listed `expo-haptics` beside
  `expo-device` and `expo-secure-store` in a real project, after `grep` in
  `android/` found nothing.
- `expo run:android` without `ANDROID_HOME` stopped at "SDK location not
  found" after the prebuild (2026-10-08).
- Gradle and Kotlin daemons stayed resident after a successful build: about
  4 GB and 2 GB RSS.
- MapLibre screen: the accessibility tree returned 24 elements and none inside
  the map; the annotated screenshot labeled about 50 there.
- `adb-ui.sh` against a real emulator: `dump` returned 14 labels with bounds,
  `tap "Chrome"` switched activity, `shot` produced 58 KB.
- Wireless debugging: `adb connect IP:port` failed where the mDNS service name
  connected, same device, network and minute.
