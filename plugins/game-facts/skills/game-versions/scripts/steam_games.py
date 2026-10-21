#!/usr/bin/env python3
"""Read Steam appmanifests and match installed game names against a prompt.

Kept apart from the hook because name matching is what produces false
positives, so it is what the self-test covers; the bash hook only forwards the
prompt. The .acf gives appid, name, buildid, LastUpdated and StateFlags per
game; it never gives the marketing version ("1.0.4"). Stdlib only.

    steam_games.py                 table of installed games
    steam_games.py --json          the same as JSON
    steam_games.py --match-stdin   read a prompt on stdin, print the context block
    steam_games.py --self-test
"""

import json
import os
import pathlib
import re
import sys
import tempfile

# Default libraries; libraryfolders.vdf, when present, adds the others
# (games on an external drive).
STEAM_ROOTS = [
    pathlib.Path.home() / ".local/share/Steam/steamapps",
    pathlib.Path.home() / "Steam/steamapps",
    pathlib.Path.home() / ".steam/steam/steamapps",
]

# Installed by Steam but not games. Matched by name, not appid: every Proton
# release gets a new appid, so an id list would go stale silently.
NOT_A_GAME = re.compile(
    r"^(Steam Linux Runtime|Proton |Proton$|Steamworks Common|SteamVR|"
    r"Steam Controller|Blender$)",
    re.I,
)

# Shorter names match almost anything; four keeps "DOOM" and drops noise.
MIN_NAME_LEN = 4

# The injected block runs on every matching prompt; keep it a hint, not a manual.
MAX_BLOCK_CHARS = 1500


def _acf_field(text: str, key: str) -> str | None:
    """A top-level field of the .acf. Shallow on purpose: the five fields used
    all sit at the first level of AppState as "key"<tab>"value"."""
    m = re.search(r'"%s"\s+"([^"]*)"' % re.escape(key), text)
    return m.group(1) if m else None


def steam_roots() -> list[pathlib.Path]:
    roots = [p for p in STEAM_ROOTS if p.is_dir()]
    for root in list(roots):
        vdf = root / "libraryfolders.vdf"
        if not vdf.is_file():
            continue
        try:
            text = vdf.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for path in re.findall(r'"path"\s+"([^"]+)"', text):
            extra = pathlib.Path(path) / "steamapps"
            if extra.is_dir() and extra not in roots:
                roots.append(extra)
    return roots


def installed_games(roots=None) -> list[dict]:
    """Installed games, sorted by name."""
    out, seen = [], set()
    for root in roots if roots is not None else steam_roots():
        for acf in sorted(root.glob("appmanifest_*.acf")):
            try:
                text = acf.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            name = _acf_field(text, "name")
            appid = _acf_field(text, "appid")
            if not name or not appid or appid in seen:
                continue
            if NOT_A_GAME.search(name) or len(name) < MIN_NAME_LEN:
                continue
            seen.add(appid)
            updated = _acf_field(text, "LastUpdated") or "0"
            out.append({
                "appid": appid,
                "name": name,
                "buildid": _acf_field(text, "buildid") or "?",
                # StateFlags 4 = installed and intact. Anything else is a
                # partial download, pending update or missing files, and the
                # buildid then does not describe what is on disk.
                "state_ok": _acf_field(text, "StateFlags") == "4",
                "updated_epoch": int(updated) if updated.isdigit() else 0,
                "manifest": str(acf),
            })
    return sorted(out, key=lambda g: g["name"].lower())


def match(prompt: str, games: list[dict]) -> list[dict]:
    """Games whose full name appears in the prompt between non-alphanumeric
    boundaries. Whole phrase, not tokens: matching "two" alone would fire on
    every arithmetic prompt; "palworld" matches, "palworldish" does not."""
    hits = []
    for g in games:
        pattern = r"(?<![0-9A-Za-z])%s(?![0-9A-Za-z])" % re.escape(g["name"])
        if re.search(pattern, prompt, re.I):
            hits.append(g)
    return hits


# The studio's Steam news feed: public, keyless and dated — what links the
# on-disk buildid to the version players see. It mixes press items; consumers
# filter on feedname == "steam_community_announcements".
NEWS_API = "https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/"


def news_url(appid: str, count: int = 5, maxlength: int = 1500) -> str:
    """The patch-notes URL for an appid. Built, never fetched: this runs in a
    hook on every prompt, where network latency costs more than the hint."""
    return f"{NEWS_API}?appid={appid}&count={count}&maxlength={maxlength}"


def render(hits: list[dict]) -> str:
    import datetime as _dt

    lines = ["The prompt names a game installed here. Before answering about its "
             "mechanics, config, patches or balance:", ""]
    for g in hits:
        when = (_dt.datetime.fromtimestamp(g["updated_epoch"]).strftime("%Y-%m-%d")
                if g["updated_epoch"] else "unknown")
        state = "" if g["state_ok"] else "  [StateFlags != 4: incomplete install or pending update]"
        lines.append(f"  {g['name']}  appid={g['appid']}  buildid={g['buildid']}  "
                     f"updated={when}{state}")
        lines.append(f"      patch notes: {news_url(g['appid'])}")
    lines += [
        "",
        "1. buildid is NOT the marketing version; never derive one from the other.",
        "2. Updated after your training cutoff means you do not know what changed. "
        "If you answer from memory, say so and give the cutoff.",
        "3. A config or save file on disk beats memory and any guide: read it.",
        "4. Read the patch notes first and list what touched the subsystem. Older "
        "sources are suspect unless a negative audit of every later version clears "
        "them; then say \"no known change since <date>\", never \"current\".",
        "5. Every number needs (value, version, source date). A search summary is "
        "not a source; count origins, not domains.",
        "Full rules: the game-versions skill.",
    ]
    return "\n".join(lines)


def _self_test() -> int:
    fails = []

    def check(cond, msg):
        if not cond:
            fails.append(msg)

    with tempfile.TemporaryDirectory() as td:
        root = pathlib.Path(td)

        def write(appid, name, buildid, updated, state="4"):
            (root / f"appmanifest_{appid}.acf").write_text(
                '"AppState"\n{\n'
                f'\t"appid"\t\t"{appid}"\n'
                f'\t"name"\t\t"{name}"\n'
                f'\t"StateFlags"\t\t"{state}"\n'
                f'\t"buildid"\t\t"{buildid}"\n'
                f'\t"LastUpdated"\t\t"{updated}"\n'
                "}\n", encoding="utf-8")

        write("1623730", "Palworld", "25094871", "1788752359")
        write("2394010", "Palworld Dedicated Server", "25080279", "1788753730")
        write("1426210", "It Takes Two", "18385016", "1754000000")
        write("105600", "Terraria", "24893155", "1755000000")
        write("1391110", "Steam Linux Runtime 2.0 (soldier)", "1", "1")
        write("1493710", "Proton Experimental", "2", "2")
        write("999999", "Half-Life", "3", "3", state="1026")

        games = installed_games([root])
        names = [g["name"] for g in games]

        check("Palworld" in names, "Palworld not found")
        check("Terraria" in names, "Terraria not found")
        check(not any("Steam Linux Runtime" in n for n in names), "Steam runtime not filtered")
        check(not any(n.startswith("Proton ") for n in names), "Proton not filtered")
        check(names == sorted(names, key=str.lower), "output not sorted by name")

        pal = next(g for g in games if g["name"] == "Palworld")
        check(pal["buildid"] == "25094871", f"wrong buildid: {pal['buildid']}")
        check(pal["appid"] == "1623730", "wrong appid")
        check(pal["state_ok"] is True, "StateFlags 4 should be intact")

        hl = next(g for g in games if g["name"] == "Half-Life")
        check(hl["state_ok"] is False, "StateFlags 1026 should not be intact")

        # --- matching ---
        m = [g["name"] for g in match("how do guilds work in palworld", games)]
        check(m == ["Palworld"], f"lowercase should match only Palworld, got {m}")

        m = [g["name"] for g in match("start the Palworld Dedicated Server", games)]
        check("Palworld Dedicated Server" in m and "Palworld" in m,
              f"long and short names should both match, got {m}")

        m = match("a prompt about kubernetes and postgres", games)
        check(m == [], f"a prompt without a game should match nothing, got {m}")

        m = match("palworldish is not the game", games)
        check(m == [], "right boundary failed: palworldish matched")

        m = match("no-palworld-branch", games)
        check([g["name"] for g in m] == ["Palworld"], "a hyphen should count as a boundary")

        m = match("it takes two hours to compile", games)
        check([g["name"] for g in m] == ["It Takes Two"],
              "the whole phrase should match even in another sense")

        m = match("this takes two hours", games)
        check(m == [], "token matching is a false positive: 'takes two' without 'it'")

        block = render(match("terraria", games))
        check("buildid=24893155" in block, "render lost the buildid")
        check("NOT the marketing version" in block, "render lost rule 1")
        check("negative audit" in block and "no known change since" in block,
              "render lost the patch fence's second exit")
        check("not a source" in block and "origins, not domains" in block,
              "render lost the source rules")
        check(len(block) < MAX_BLOCK_CHARS, f"injected block grew to {len(block)} chars")

        # --- patch notes: the URL is built, never fetched ---
        u = news_url("1623730")
        check(u.startswith("https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/"),
              f"wrong endpoint: {u}")
        check("appid=1623730" in u, f"appid missing from the URL: {u}")
        check("&count=" in u and "&maxlength=" in u, f"count/maxlength missing: {u}")
        check(news_url("105600") != news_url("1623730"),
              "different appids should give different URLs")
        check(news_url("1623730", count=1) != news_url("1623730", count=5),
              "count should be in the URL")
        check("api.steampowered.com" in block, "render should cite the matched game's patch notes")

    for f in fails:
        print(f"FAIL: {f}", file=sys.stderr)
    print(f"self-test: {len(fails)} failure(s)")
    return 1 if fails else 0


def main() -> int:
    args = sys.argv[1:]
    if "--self-test" in args:
        return _self_test()

    if "--match-stdin" in args:
        prompt = sys.stdin.read()
        if not prompt.strip():
            return 0
        hits = match(prompt, installed_games())
        if hits:
            print(render(hits))
        return 0

    games = installed_games()
    if "--json" in args:
        json.dump(games, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
    else:
        for g in games:
            flag = "" if g["state_ok"] else "  (incomplete install)"
            print(f"{g['appid']:>10}  {g['name']:<36} buildid={g['buildid']}{flag}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except BrokenPipeError:
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        sys.exit(0)
