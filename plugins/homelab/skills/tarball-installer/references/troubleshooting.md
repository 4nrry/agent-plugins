# Troubleshooting and per-app recipes

Contents:
- [App dies at startup with a sandbox error (AppArmor / user namespaces)](#apparmor)
- [Missing shared libraries](#libs)
- [Wrong or missing icon in the menu](#icon)
- [App not in the menu at all](#menu)
- [The vendor's own .desktop, and what gets rewritten](#vendor)
- [Version directory name is stale after a self-update](#stale)
- [`--system` install of a self-updating app](#system-selfupdate)
- [Per-app recipes](#recipes)

<a name="apparmor"></a>
## App dies at startup with a sandbox error

Since Ubuntu 24.04, `kernel.apparmor_restrict_unprivileged_userns=1` blocks unprivileged user namespaces. Chromium/Electron apps and Firefox forks use those for their sandbox. The shipped AppArmor profiles only cover deb and snap paths, so a tarball install is unprotected by construction — Mozilla documents this for Firefox tarballs.

Check the current setting first; it isn't always on:

```bash
sysctl kernel.apparmor_restrict_unprivileged_userns
```

If it's `0`, this is not your problem — keep looking.

If it's `1` and the app fails, add a profile naming the *real* binary path (the wrapper in `~/.local/bin` is not what the kernel sees). For a per-user install of `<app>`:

```
# /etc/apparmor.d/<app>
abi <abi/4.0>,
include <tunables/global>
profile <app> /home/*/.local/opt/<app>/*/<app>{,-bin} flags=(unconfined) {
  userns,
  include if exists <local/<app>>
}
```

```bash
sudo apparmor_parser -r /etc/apparmor.d/<app>
```

The glob over `*/` covers every installed version, so the profile survives upgrades. `flags=(unconfined)` means "no confinement beyond allowing userns" — it grants the app the namespace permission back without pretending to write a real confinement policy.

Disabling the sysctl globally (`sudo sysctl -w kernel.apparmor_restrict_unprivileged_userns=0`) works but removes the protection for everything on the machine. Use it to confirm the diagnosis, then prefer the per-app profile. If you do suggest the global switch, say plainly what it turns off.

<a name="libs"></a>
## Missing shared libraries

```bash
ldd ~/.local/opt/<app>/current/<binary> | grep 'not found'
```

Then install the packages providing them (`apt-file search <lib>` if you need to map a name). Common on minimal or KDE-only systems: `libgtk-3-0t64`, `libnss3`, `libasound2t64`, `libgbm1`, `libxss1`. Never copy `.so` files into the app directory — that breaks on the next system upgrade.

<a name="icon"></a>
## Wrong or missing icon in the menu

The script copies the icon into `hicolor` and writes a bare name (`Icon=zen`) rather than a path, which is what lets icon themes and HiDPI scaling work. If the icon is missing, the tarball had no usable PNG where autodetection looked — common for Electron apps, which bury it inside `resources/app.asar`.

Don't place it by hand: `--icon` accepts an absolute path to any file, so the `.desktop` keeps its `Icon=` line on every future upgrade instead of losing it each reinstall. Park the extracted PNG outside the version directories and point at it:

```bash
cp <icon.png> ~/.local/opt/<app>/icon.png
tarball-install --name <app> --icon ~/.local/opt/<app>/icon.png ... <tarball>
```

Pulling an icon out of an `app.asar` needs no npm — the format is a 16-byte header, a JSON index, then the payload:

```bash
python3 - <<'EOF'
import json, struct, pathlib
p = pathlib.Path("resources/app.asar")          # adjust the path
with p.open('rb') as f:
    _, hdr_size, _, json_len = struct.unpack('<IIII', f.read(16))
    hdr = json.loads(f.read(json_len)); base = 8 + hdr_size
    e = hdr['files']['icon.png']                 # list(hdr['files']) if the name differs
    f.seek(base + int(e['offset']))
    pathlib.Path("icon.png").write_bytes(f.read(e['size']))
EOF
```

An SVG goes in `hicolor/scalable/apps/` instead and scales better — prefer it when the tarball ships one.

### The failure that looks like a stale cache

An app installed with a large icon and nothing else — 512px only — shows either a generic icon or, worse, *another app's icon*. Both look exactly like a cache that hasn't caught up, and waiting doesn't fix either.

The cause is the freedesktop icon-name fallback: when the menu asks for 32 or 48px and finds no usable size for `Icon=antigravity-ide`, it truncates the name at the hyphen and retries `antigravity` — a different application that happens to have small sizes installed. Silent, and it renders as "the two entries have the same icon".

The script handles this from v1.3 on: any icon over 256px is also written at 128 and 256, using `magick`/`convert` or Pillow. If neither exists on the machine it says so rather than installing the trap. To repair an install made before that, or one that hit the warning:

```bash
python3 - <<'EOF'
from PIL import Image
import pathlib
src = pathlib.Path.home()/".local/opt/<app>/icon.png"
for s in (128, 256):
    d = pathlib.Path.home()/f".local/share/icons/hicolor/{s}x{s}/apps"
    d.mkdir(parents=True, exist_ok=True)
    Image.open(src).resize((s, s), Image.LANCZOS).save(d/"<app>.png")
EOF
gtk-update-icon-cache -qtf ~/.local/share/icons/hicolor
kbuildsycoca6 --noincremental      # KDE only
```

Only after the sizes are in place is "it's the cache" worth entertaining. Diagnosing in that order matters: two apps sharing a name prefix is common (`foo` and `foo-ide`, `code` and `code-insiders`), so the fallback fires more often than it seems.

### The failure that really is the cache

The other one looks the same on screen and has the opposite fix. After an uninstall-then-reinstall — swapping the `.desktop`, say — the menu can keep showing a generic icon for an entry whose files are all correct, because `plasmashell` is long-lived and holds the already-rendered entry. Rebuilding the caches doesn't dislodge it; interacting with the entry, or restarting the shell, does.

Prove which one you have before touching anything, with two independent resolvers:

```bash
kiconfinder6 <name>          # KIconLoader
```

```python
import os; os.environ["QT_QPA_PLATFORM"] = "offscreen"    # QIconLoader, o que o Plasma usa
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import QSize
app = QApplication([])
QIcon.setThemeSearchPaths([os.path.expanduser("~/.local/share/icons"), "/usr/share/icons"])
QIcon.setFallbackThemeName("hicolor"); QIcon.setThemeName("breeze")
i = QIcon.fromTheme("<name>")
print(i.isNull(), i.availableSizes(), i.pixmap(QSize(48, 48)).size())
```

Both run in fresh processes, so neither can inherit the desktop's stale state. If they resolve the icon and produce a real pixmap, the install is fine and only the shell is behind:

```bash
kquitapp6 plasmashell && kstart plasmashell
```

Resist the urge to rasterize an SVG into extra PNG sizes "to be safe" here — a scalable-only icon resolves correctly, and adding sizes on top of a working install just buries the actual cause under files the script won't recreate on the next upgrade.

If the taskbar shows a generic icon only while the app is *running*, the culprit is `StartupWMClass`. Find the real value with `xprop WM_CLASS` (X11) or by checking the app's own window class, then set `--wm-class`.

<a name="menu"></a>
## App not in the menu at all

```bash
desktop-file-validate ~/.local/share/applications/<app>.desktop
update-desktop-database ~/.local/share/applications
kbuildsycoca6 --noincremental      # KDE only
```

Validation errors are usually a missing `Type=Application`, a `Categories` value without its trailing `;`, or an `Exec` pointing at a path that doesn't exist. On Wayland sessions the menu sometimes needs a logout to notice a brand-new `.desktop`.

<a name="vendor"></a>
## The vendor's own `.desktop`, and what gets rewritten

From v1.4 the script looks for a `.desktop` shipped inside the tarball — root first, then `*/applications/*.desktop` — and builds the menu entry from it instead of from scratch. Generating one by hand silently drops things that are hard to notice missing: translated `Name`/`Comment`/`GenericName`, `Keywords` (menu search by "sculpting" or "render" rather than by app name), and `PrefersNonDefaultGPU=true`, which on a hybrid-GPU machine is what makes the desktop offer — or default to — the discrete card.

Three keys can't survive the move and are rewritten or dropped:

| key | what happens | why |
|---|---|---|
| `Exec` | program replaced by the wrapper, arguments kept | the vendor's path doesn't exist here; the field code (`%f`, `%U`) is the app's own choice and worth keeping |
| `TryExec` | pointed at the wrapper | otherwise the entry hides itself as "not installed" |
| `Icon` | replaced by the installed icon name | an absolute path into the vendor tree would dangle |
| `Path` | dropped | points at the vendor's build directory |
| `DBusActivatable` | dropped | promises a D-Bus service this install doesn't register, and some desktops then fail to launch the app |

The search only accepts regular files, which matters more than it sounds: the JBR that JetBrains bundles (Android Studio included) contains *directories* named `java.desktop` and `jdk.unsupported.desktop` — JDK module names, not menu entries.

Environment prefixes are handled: `Exec=env LC_ALL=C app --gpu %F` becomes the wrapper plus `--gpu %F`. Desktop Actions are rewritten the same way, and `--action` entries are appended to whatever the vendor already defined.

Any flag passed explicitly overrides the vendor — and `--title`/`--comment` also drop the vendor's localized variants of that key, otherwise `Name[pt_BR]` would quietly win over the `Name` you asked for. `--vendor-desktop <path>` forces a specific file; `--no-vendor-desktop` goes back to generating the entry from the flags alone.

<a name="stale"></a>
## Version directory name is stale after a self-update

Expected. The directory name is a snapshot of the version at install time; when the app updates itself in place, the files change and the name doesn't. It's cosmetic — `current` still points at the right place and everything keeps working. Re-running `tarball-install` with a fresh tarball re-syncs the name. Don't rename the directory by hand: the `current` symlink and the wrapper both reference it.

<a name="system-selfupdate"></a>
## `--system` install of a self-updating app

If the user insists on `/opt` for an app that updates itself, install it and be explicit about the consequence: the in-app updater will fail with a permission error, and updates become a manual re-run of `tarball-install --system` with a new tarball. Do not paper over it with `chown -R $USER /opt/<app>` — that yields a single-user install sitting in a multi-user location, which is the worst of both.

<a name="recipes"></a>
## Per-app recipes

**Zen Browser** (Firefox fork, self-updating — per-user only)

```bash
tarball-install --name zen --title "Zen Browser" \
  --exec zen --icon browser/chrome/icons/default/default128.png \
  --args '%u' --categories 'Network;WebBrowser;' \
  --mime 'text/html;text/xml;application/xhtml+xml;x-scheme-handler/http;x-scheme-handler/https;' \
  --action 'new-window|New Window|--new-window %u' \
  --action 'new-private-window|New Private Window|--private-window %u' \
  --action 'profile-manager-window|Profile Manager|--ProfileManager' \
  zen.linux-x86_64.tar.xz
```

Version comes from `application.ini` automatically. Profiles live in `~/.zen`, untouched by reinstalls. Upstream's own installer is per-user for the same self-update reason.

**VS Code** (self-updating; the tarball's root is `VSCode-linux-x64`)

```bash
tarball-install --name code --title "Visual Studio Code" \
  --exec code --icon resources/app/resources/linux/code.png \
  --args '%F' --categories 'Development;IDE;TextEditor;' \
  code-stable.tar.gz
```

**Obsidian / Electron apps** — the binary is usually named after the app at the root; `--exec` is rarely needed. Categories `Office;`, and `--args '%U'` if it registers URI handlers. `resources/app-update.yml` is the tell that it self-updates, so keep it per-user.

**Antigravity** (Electron, self-updating, version and icon both inside `app.asar`)

```bash
tarball-install --name antigravity --title "Antigravity" \
  --exec antigravity --app-version <ver> --icon ~/.local/opt/antigravity/icon.png \
  --args '%F' --categories 'Development;IDE;TextEditor;' \
  --mime 'text/plain;inode/directory;' Antigravity.tar.gz
```

The tarball root is `Antigravity-x64/`, so autodetection of the name would be wrong — pass `--name`. Read the version from `package.json` at the root of `app.asar` (same snippet as above, swapping `icon.png` for `package.json`); without it the directory is stamped with the date.

**Blender** (no self-updater, so `--system` is also fine; ships `blender.desktop` and `blender.svg` at the root)

```bash
tarball-install --name blender --app-version 5.2.0 \
  --exec blender --icon blender.svg blender-5.2.0-linux-x64.tar.xz
```

`--name` is needed because the tarball is `blender-5.2.0-linux-x64` and the slug would keep the version. Everything else — categories, `application/x-blender`, `StartupWMClass=Blender`, `PrefersNonDefaultGPU` — comes from the vendor `.desktop`. There are two executables at the root: `blender` is the one upstream's own entry uses.

**JetBrains IDEs** (self-updating; launcher under `bin/`)

```bash
tarball-install --name idea --title "IntelliJ IDEA" \
  --exec bin/idea --icon bin/idea.png \
  --args '%f' --categories 'Development;IDE;' ideaIC-*.tar.gz
```

**CLI tools** (Node, Go toolchains, static binaries) — no menu entry, and the wrapper only exposes one command:

```bash
tarball-install --name node --exec bin/node --no-desktop node-v22.tar.xz
```

When a tarball ships a whole `bin/` directory that must be on PATH (Node's `npm`/`npx`, a Go toolchain), the single wrapper isn't enough. Add the extras alongside it:

```bash
for c in npm npx; do
  printf '#!/bin/sh\nexec "%s/.local/opt/node/current/bin/%s" "$@"\n' "$HOME" "$c" > ~/.local/bin/$c
  chmod +x ~/.local/bin/$c
done
```

This keeps the indirection through `current`, so a version bump moves every command at once.
