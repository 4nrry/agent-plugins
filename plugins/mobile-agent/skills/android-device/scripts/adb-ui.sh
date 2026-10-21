#!/usr/bin/env bash
# UI automation by TEXT — inspect and tap the screen without reading screenshots.
#
#   adb-ui.sh dump                list label + bounds of the current screen
#   adb-ui.sh tap "Continue"      tap the center of the best matching node
#   adb-ui.sh tapxy 720 803       tap absolute coordinates
#   adb-ui.sh type "ABC123"       type text
#   adb-ui.sh esc                 close the keyboard
#   adb-ui.sh shot [out.jpg]      downscaled screenshot, safe to read
#
# With more than one device connected, export ANDROID_SERIAL — adb honors it.
#
# Two decisions that look like details but are not:
#
# 1. The dump comes via `exec-out ... /dev/tty`, not a file. `uiautomator dump
#    /sdcard/ui.xml` sometimes fails silently and leaves the previous file, so
#    you read a stale tree and think the screen froze. stdout has no stale state.
#
# 2. `esc` sends keyevent 111, not 4 (BACK). In a React Native app, BACK with no
#    keyboard up navigates back, and with nothing to go back to some apps show a
#    full-screen error that blocks the flow. ESC closes the keyboard only.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PARSER="$HERE/adb_ui.py"

die() { printf '%s\n' "$*" >&2; exit 1; }

usage() { sed -n '3,9p' "$0" | sed 's/^# \?//' >&2; }

# Without a valid subcommand, print usage — asking for help must not need a device.
case "${1:-}" in
  dump|tap|tapxy|type|esc|shot) ;;
  *) usage; exit 2 ;;
esac

command -v adb >/dev/null 2>&1 || die "adb is not on PATH."
[[ -f "$PARSER" ]] || die "parser missing: $PARSER"

devices=$(adb devices 2>/dev/null | grep -cE '\sdevice$' || true)
case "$devices" in
  0) die "No device connected. Check with \`adb devices\`." ;;
  1) ;;
  *) [[ -n "${ANDROID_SERIAL:-}" ]] || die \
       "$devices devices connected. Export ANDROID_SERIAL to choose one." ;;
esac

dump() { adb exec-out uiautomator dump /dev/tty 2>/dev/null; }

# A dump with no labeled node almost never means a frozen app: GL surfaces (map,
# video, WebView, canvas) simply do not appear in the accessibility tree. Saying
# so here avoids the wrong diagnosis.
no_tree() {
  printf '%s\n' \
    "The accessibility tree came back empty on this screen." \
    "" \
    "That is usually NOT a frozen app. GL surfaces — map, video," \
    "WebView, canvas — do not appear in the UI Automator dump." \
    "" \
    "Visual path, if the \`android\` CLI is installed:" \
    "  android screen capture --annotate -o shot.png" \
    "  adb shell input \$(android screen resolve --screenshot shot.png --string \"tap #N\")" \
    "" \
    "Without it, what is left is absolute coordinates (\`tapxy\`) and pixel-color checks." >&2
}

case "${1:-}" in
  dump)
    out=$(dump | python3 "$PARSER" list)
    if [[ -z "$out" ]]; then no_tree; exit 3; fi
    printf '%s\n' "$out"
    ;;
  tap)
    [[ $# -ge 2 ]] || die "usage: adb-ui.sh tap <text>"
    tree=$(dump)
    xy=$(printf '%s' "$tree" | python3 "$PARSER" find "$2") || xy=""
    if [[ -z "$xy" ]]; then
      if [[ -z "$(printf '%s' "$tree" | python3 "$PARSER" list)" ]]; then
        no_tree
      else
        # The printf format is single-quoted on purpose: it contains literal
        # backticks, which double quotes would turn into command substitution.
        # shellcheck disable=SC2016
        printf 'Could not find %s on screen. `adb-ui.sh dump` shows what is there.\n' "$2" >&2
      fi
      exit 3
    fi
    printf 'tap %s -> %s\n' "$2" "$xy"
    # shellcheck disable=SC2086  # xy is "X Y", two arguments on purpose.
    adb shell input tap $xy
    ;;
  tapxy)
    [[ $# -ge 3 ]] || die "usage: adb-ui.sh tapxy <x> <y>"
    adb shell input tap "$2" "$3"
    ;;
  type)
    [[ $# -ge 2 ]] || die "usage: adb-ui.sh type <text>"
    # `adb shell` hands the line to the DEVICE shell, which re-splits on spaces
    # and interprets `;`, `&`, `$`. Untreated, `type "ABC 123"` types only "ABC"
    # and drops the rest silently. So: space becomes %s (`input text` takes one
    # argument) and the text is single-quoted, with inner single quotes escaped.
    text=${2//\'/\'\\\'\'}
    text=${text// /%s}
    # If the app still reloads mid-typing, suspect a dev-menu shortcut: in dev
    # builds some keys are shortcuts. Type in chunks, splitting before that key.
    adb shell input text "'$text'"
    ;;
  esc)
    adb shell input keyevent 111
    ;;
  shot)
    dest="${2:-shot.jpg}"
    tmp=$(mktemp --suffix=.png)
    trap 'rm -f "$tmp"' EXIT
    adb exec-out screencap -p > "$tmp" 2>/dev/null
    [[ -s "$tmp" ]] || die "screencap returned empty."
    # Downscaling is not cosmetic: a full screenshot is several MB, and reading
    # it in an agent session is a known way to run out of memory.
    # The destination must be absolute: with no slash in the path, vipsthumbnail
    # writes next to the INPUT (in /tmp), so the file would land there and this
    # script would print a path that does not exist.
    case "$dest" in /*) abs="$dest" ;; *) abs="$PWD/$dest" ;; esac
    if command -v vipsthumbnail >/dev/null 2>&1; then
      vipsthumbnail "$tmp" --size 640x -o "${abs}[Q=85]" 2>/dev/null
      [[ -s "$abs" ]] || die "vipsthumbnail did not write $abs."
    elif command -v magick >/dev/null 2>&1; then
      magick "$tmp" -resize 640x "$dest"
    else
      cp "$tmp" "${dest%.jpg}.png"
      dest="${dest%.jpg}.png"
      printf 'Neither vipsthumbnail nor magick found: saved the full PNG. Be careful reading it.\n' >&2
    fi
    printf '%s\n' "$dest"
    ;;
  *)
    die "unhandled subcommand: $1"
    ;;
esac
