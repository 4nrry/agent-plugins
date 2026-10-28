---
name: expo-metro
description: Covers what fails silently in an Expo / React Native project — a prebuild that does not run and says nothing, a Metro serving another checkout's bundle, a missing node_modules that breaks only the bundler while tsc and jest pass, native modules that never reached the device, and EXPO_PUBLIC_ variables that ship secrets inside the APK. Use before a local build, before editing app.json or a config plugin, and when a change "has no effect" with no error.
---

# Expo / Metro

The pattern here is apparent success: exit 0, `BUILD SUCCESSFUL`, and the
change you expected is not there.

## The prebuild that does not run

With `android/` present, `expo run:android` does not prebuild, and says
nothing. Changes to `app.json`, config plugins or icons are ignored; Gradle
reuses old resources and finishes suspiciously fast. Regenerate explicitly:

```bash
npx expo prebuild --platform android --clean
```

`--clean` deletes the native directories first; without it changes are
layered on old files. Gradle's `> Task :x:preBuild` lines are not Expo's
prebuild — `grep prebuild` matches them.

## The SDK does not reach a non-interactive shell

Ubuntu's `~/.bashrc` returns early for non-interactive shells, so an
`ANDROID_HOME` set there is empty in any agent tool, and Gradle fails minutes
later with `SDK location not found`. Export it in the command:

```bash
export ANDROID_HOME="$HOME/Android/Sdk" JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
export PATH="$PATH:$ANDROID_HOME/platform-tools:$ANDROID_HOME/emulator"
npx expo run:android
```

`sdk.dir` in `android/local.properties` also works but is deleted by
`prebuild --clean`.

## A new native module is not in the build

After adding a package with native code, `npm install`, `tsc` and Fast
Refresh all succeed while the device runs the old binary. Optional Expo
modules load through `requireOptionalNativeModule`, which returns `null`
instead of throwing, so the call just does nothing. Rebuild, then prove the
module was linked:

```bash
npx expo prebuild --platform android --clean
npx expo run:android
npx expo-modules-autolinking resolve -p android --json | jq -r '.modules[].packageName'
```

The build leaves Gradle and Kotlin daemons resident (GBs of RSS). Stop the
Gradle one with `./gradlew --stop` in `android/`.

## One Metro per port

Metro listens on 8081 (React Native's default). A second Metro does not start
cleanly, and the dev client keeps talking to the first — you edit one checkout
and see another's bundle. Find the owner with `ss -ltnp | grep ':8081'` and
`readlink /proc/<pid>/cwd`. Prefer another port (`--port 8082`, plus the
matching deep link) over killing a process that may be another session's.

## node_modules missing breaks only Metro

In a worktree or checkout without its own `node_modules`, `npx expo`, `tsc`
and `jest` resolve upward and pass; Metro returns 404 for the bundle with an
unresolved module.

Do not symlink another checkout's `node_modules`. With expo-router, routes
resolve through the real path, so the worktree's Metro serves the *other*
checkout's `app/` directory: the device shows a stale screen, or "Welcome to
Expo", and no error. Copy it as hardlinks instead, which takes seconds and no
extra disk on the same filesystem:

```bash
cp -al <main-checkout>/node_modules node_modules
```

Either way the copy runs the app but must not produce a build: it holds the
other branch's dependencies. With pnpm, `pnpm install` in the worktree is
already fast and links from the store.

## Metro belongs to the session

With agents moving between worktrees, a Metro left running in one terminal
serves whichever checkout started it. Start Metro from the worktree being
changed, on its own port, and stop it when the task ends:

- Run it as a background task or a harness-managed dev server, never in a
  terminal someone has to watch. Watch the log for the ready line and for
  `Bundling failed`, not by polling.
- Pass the port explicitly (`--port $PORT`) and use the same port in
  `adb reverse tcp:$PORT tcp:$PORT` and in the dev-client deep link. A launch
  config with automatic ports only helps if the command reads the assigned
  `PORT`; a hardcoded `--port 8081` in its arguments defeats it.
- Gitignored env files (`.env.local` with bench logins) are not in a new
  worktree. Copy them, or list them in the harness's worktree include file.
- One phone talks to one Metro. Before taking the device, check who owns the
  bundler ports and tunnels (`/mobile-agent:preflight`).
- Prove the worktree's code reached the device: change a visible string only
  in the worktree and read it back from the screen.

## Fast Refresh can stick

Renaming or adding a module constant across two edits can leave HMR in an
intermediate state with a render error and a clean typecheck. Reload before
hunting the bug. When a test depends on new code reaching the device, change
a visible marker on screen to prove it arrived.

## EXPO_PUBLIC_ ships inside the artifact

Every `EXPO_PUBLIC_` variable is inlined into the bundle at build time and is
readable in the APK. A `.env.local` with a bench credential produces an
artifact that contains it. Build without dotenv files with
`EXPO_NO_DOTENV=1 npx expo ...`, and check an artifact before distributing it
(the bundle is Hermes bytecode, so extract strings first):

```bash
unzip -p app.apk assets/index.android.bundle | strings -n 6 | grep -F "<value>"
```

## The dev client opens on the launcher

The documented paths are the detected LAN bundler, the logged-in Expo account,
or the QR code. In automation, the deep link
`<scheme>://expo-development-client/?url=http%3A%2F%2Flocalhost%3A8081` is a
useful shortcut, not the documented mechanism. Close the developer menu that
opens on first load before concluding the screen is stuck.
