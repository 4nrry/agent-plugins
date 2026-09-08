---
name: tarball-installer
description: Install an application tarball (.tar.gz/.tar.xz/.tar.bz2/.tar.zst) on Ubuntu/Kubuntu/Debian the standardized way — versioned directory plus a `current` symlink, a wrapper on PATH, a validated .desktop entry, and the icon in hicolor — using the bundled `tarball-install` script. Use this whenever the user has a downloaded app tarball to install, asks where to extract it or whether it belongs in /opt vs /usr/local vs the home directory, wants a menu entry or launcher for a manually installed app, or wants to update, roll back, list, or uninstall one. Trigger it even when the user just says "install this tar.xz" or names a specific app (Zen, VS Code, Obsidian, JetBrains, Node) without mentioning any convention, and whenever a manual install is about to be improvised with raw tar/mv/ln commands.
---

# Standardized tarball installs on Ubuntu/Kubuntu

Hand-rolled tarball installs rot. Files land somewhere different each time, nothing records what was installed, there's no way back to the previous version, and half the time the app never shows up in the menu. This skill replaces improvisation with one repeatable layout, applied by a bundled script.

## The layout

Per-user (default):

```
~/.local/opt/<app>/<version>/   application files
~/.local/opt/<app>/current  ->  symlink to the active version
~/.local/bin/<app>              wrapper on PATH, execs through `current`
~/.local/share/applications/<app>.desktop
~/.local/share/icons/hicolor/<size>x<size>/apps/<app>.png
```

System-wide (`--system`): the same shape in `/opt/<app>` with `/usr/local/bin`, `/usr/local/share/applications` and `/usr/local/share/icons`.

Two properties make this worth keeping: the wrapper and the `.desktop` point at `current`, never at a version, so switching versions is a single `ln -sfn` and nothing else breaks; and every path is predictable, so uninstalling is exact instead of archaeological.

## Before installing: is a tarball even the right answer?

Spend ten seconds checking `apt-cache policy <app>`, and mention it if a Flatpak or an official `.deb` exists. Packaged installs get security updates for free. This is a note to the user, not a veto — if they downloaded a tarball they usually have a reason (newer version, no package, avoiding Snap). Say it once, then install what they asked for.

## Step 1 — make sure the tool is present

The script lives at `scripts/tarball-install` inside this skill. Install or refresh it before use:

```bash
mkdir -p ~/.local/bin
SKILL_DIR="${CLAUDE_PLUGIN_ROOT}/skills/tarball-installer"
cmp -s "$SKILL_DIR"/scripts/tarball-install ~/.local/bin/tarball-install \
  || cp "$SKILL_DIR"/scripts/tarball-install ~/.local/bin/tarball-install
chmod +x ~/.local/bin/tarball-install
```

Run `~/.local/bin/tarball-install --help` if you need the current flag list — trust the script's own help over memory.

## Step 2 — look inside the tarball first

Never install blind. What you find here decides the flags:

```bash
tar -tf <file> | head -40
```

Read it for four things:

- **The executable.** Firefox-based apps ship a launcher script next to a `*-bin`; Electron apps ship a binary named after the app; JetBrains hides it in `bin/*.sh`. Pass `--exec` whenever autodetection would be ambiguous.
- **A bundled updater** (`updater`, `*.AppImage`, an `updates/` dir, an Electron `resources/app-update.yml`). This decides Step 3.
- **A version** (`application.ini`, a versioned top-level directory). The script reads `application.ini` itself; otherwise pass `--app-version` so the directory isn't just a date.
- **A `.desktop` file.** Blender, GIMP and many others ship the exact entry their distro packages use: translated `Name`/`Comment`/`GenericName`, `Keywords` so menu search finds the app by what it does, and keys nobody would think to pass by hand — `PrefersNonDefaultGPU=true` is what makes a hybrid-GPU machine offer the discrete card. The script finds it automatically and reuses all of it, rewriting only what points at the binary (`Exec`, `TryExec`, `Icon`) and dropping what can't survive the move (`Path`, `DBusActivatable`). Explicit flags still win over the vendor's values. Use `--vendor-desktop <path>` when autodetection misses it and `--no-vendor-desktop` to build the entry from scratch instead.
- **An icon** — usually under `share/icons`, `browser/chrome/icons/default/`, or a top-level `*.png`. Electron apps often ship none loose, keeping it inside `resources/app.asar`; extract it once, park it at `~/.local/opt/<app>/icon.png` (outside the version directories, so upgrades don't touch it) and pass that absolute path to `--icon`. The hicolor size comes from the image's real dimensions, not its filename, and anything over 256px is also installed at 128 and 256 — a large-only icon makes the menu fall back to a *different* app's icon whenever the names share a prefix.

## Step 3 — choose per-user or `--system`

Default to per-user. Reach for `--system` only when the app has no self-updater *and* the user wants it available to every account on the machine.

The reason is concrete: apps with a built-in updater — Firefox and its forks (Zen, LibreWolf), VS Code, JetBrains, Obsidian — write into their own install directory when they update. Root-owned files in `/opt` make that fail with a permission error, and the usual "fixes" are worse: `chown -R $USER /opt/app` recreates a home-directory install with extra steps, and running a browser under `sudo` is a genuinely bad idea. Upstream agrees — Zen's own installer puts everything under `$HOME` and never calls `sudo`.

If the user explicitly asks for `/opt` on a self-updating app, install it there and tell them the in-app updater will fail, so the choice is theirs and not a surprise.

## Step 4 — run it

```bash
tarball-install --name zen --title "Zen Browser" \
  --exec zen --icon browser/chrome/icons/default/default128.png \
  --args '%u' --categories 'Network;WebBrowser;' \
  --mime 'text/html;x-scheme-handler/http;x-scheme-handler/https;' \
  --action 'new-private-window|New Private Window|--private-window %u' \
  ~/Downloads/zen.linux-x86_64.tar.xz
```

Flags worth knowing: `--name` (slug, also the command name), `--title` (menu label), `--exec` (path *relative to the extracted root*), `--icon` (relative to that root, or an absolute path to a file outside the tarball), `--app-version` (the app's version label — `--version` alone prints the script's own version), `--args` (`%u` for anything that opens URLs, `%F` for file handlers), `--categories`, `--mime`, `--comment`, `--action 'id|Label|args'` (repeatable, right-click menu entries), `--wm-class`, `--terminal`, `--vendor-desktop` / `--no-vendor-desktop`, `--no-desktop` (CLI tools), `--keep N`, `--system`.

When the tarball ships its own `.desktop`, most of these become unnecessary — `Categories`, `MimeType`, `StartupWMClass` and the `Exec` field code all come from it. Pass only what you actually want to change:

```bash
tarball-install --name blender --app-version 5.2.0 \
  --exec blender --icon blender.svg blender-5.2.0-linux-x64.tar.xz
```

Write `--title`, `--comment` and action labels in the language of the user's desktop, and check it (`echo $LANG`) rather than matching the language of the conversation — they are different things. A `Name=` or `Comment=` with no locale suffix is displayed in *every* locale, so a label written in the wrong language sits in the menu next to the system's own entries forever, and no amount of relaunching fixes it. Localized keys (`Comment[pt_BR]=`) are how a `.desktop` carries more than one language, and the script doesn't write them — only the vendor's own file brings those.

Getting `Categories` right is what places the app in the correct Kubuntu menu section: `Network;WebBrowser;`, `Development;IDE;`, `Office;`, `AudioVideo;`, `Graphics;`, `Utility;`. And `--args '%u'` matters more than it looks — without it, a browser installed this way can't be set as the default handler for links.

For a pure CLI tool, `--no-desktop` and let the wrapper do the work.

## Step 5 — verify, then report

Confirm rather than assume:

```bash
~/.local/bin/<app> --version
desktop-file-validate ~/.local/share/applications/<app>.desktop
tarball-install --list
```

Some GUI apps have no `--version`; launching them from the menu is the real test, so say so instead of claiming it works.

Then tell the user where things landed, the exact command to remove it, and — the one that actually bites — that `~/.local/bin` only enters `$PATH` after the next login if the directory was just created. Ubuntu's `~/.profile` adds it conditionally at login, so a directory created five minutes ago isn't on PATH yet in the current shell. Give them `export PATH="$HOME/.local/bin:$PATH"` for the session.

## Day two

```bash
tarball-install --list                              # what's installed, and at which version
tarball-install <same flags> newer.tar.xz           # upgrade: new dir, current repointed, old pruned to --keep
ln -sfn ~/.local/opt/<app>/<old> ~/.local/opt/<app>/current   # roll back, instantly
tarball-install --uninstall <app> [--system]        # remove app, wrapper, .desktop, icon
```

Uninstall deliberately leaves user data (`~/.config/<app>`, `~/.<app>`) alone — mention that so nobody assumes a clean wipe, and point at the directories if they want one.

## When something misbehaves

Read `references/troubleshooting.md` for AppArmor's user-namespace restriction on Ubuntu 24.04+ (the usual cause of a browser or Electron app dying at startup with a sandbox error), missing shared libraries, apps that ignore their `.desktop` icon, stale version directory names after a self-update, and per-app recipes for Zen, VS Code, Obsidian, JetBrains and plain CLI tarballs.
