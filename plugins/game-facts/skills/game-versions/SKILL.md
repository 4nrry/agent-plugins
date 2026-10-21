---
name: game-versions
description: Pins the installed version of a game before answering about its mechanics, config, patches, balance or "best settings", instead of answering from training memory that ages with every patch. Covers Steam appmanifests (appid, buildid, LastUpdated), why buildid is not the marketing version, where the player-visible version lives, games outside Steam, and the rule that the config file on disk beats any guide. Use when a task mentions a game, a save file, a server .ini, patch notes, or "what is the best config for".
---

# Game version before the answer

Training memory has a date; games have patches that rename keys, change
defaults and remove mechanics. Get the version from the disk — never ask the
user for what is on their disk.

## 1. Read the disk

```bash
python3 scripts/steam_games.py          # table of installed games
python3 scripts/steam_games.py --json   # appid, name, buildid, updated_epoch, state_ok
```

It reads `appmanifest_<appid>.acf` in every Steam library and skips runtimes
and Proton. `StateFlags` other than 4 means a partial download or pending
update: the `buildid` then describes what Steam wants, not what is on disk.

**`buildid` is not the marketing version.** The `.acf` never stores "1.0.4",
and there is no formula between the two. The player-visible version comes from
the game itself (a dedicated server usually prints it at boot), the title
screen, a version file in the install, or the official patch notes. If none is
available, report the `buildid` and say the marketing version is unknown.

Compare `LastUpdated` with your training cutoff. Updated after it means you do
not know what changed; say so.

Outside Steam, see [references/launchers.md](references/launchers.md).

## 2. Route the question

```
A value of THIS install (a key, current state, what happened here)?  -> LOCAL: read the file, no network
Data shipped with the game (default, level, cost, what changed)?     -> FACTUAL
A ranking, superlative, route, or "is it worth it"?                  -> META
```

"What value should I use for X?" is both: FACTUAL for the range and the
mechanic, META for the recommendation. Answer them separately and label each.

For LOCAL, compare the shipped defaults with the active file to see what was
changed here: `diff <(tr ',' '\n' < Default<Game>Settings.ini | sort) <(tr ',' '\n' < <Game>Settings.ini | sort)`.
Editing the defaults file has no effect.

## 3. Changelog first, then the patch fence

Before opening any guide, read the official patch notes (the Steam news feed
by appid; the hook injects the URL) and list every entry that touches the
question's subsystem, back to the last patch that changed it. That date is the
**patch fence**: older sources are suspect, however good. Bug fixes count —
a guide may have measured a broken build honestly.

The fence is satisfied by either:

1. a source newer than the last patch that touched the subsystem, or
2. a **negative audit**: you read the notes for every version between the
   source's date and today, named them, and none touches the subsystem.

Route 2 allows "no known change since <source date>", never "current":
numeric rebalances often go unlisted. Not having looked satisfies neither.

## 4. Weigh sources

- Every number carries **(value, version, source date)**. Missing one, state
  the gap instead of the number.
- A source claiming version V but dated before V shipped is disqualified.
- A search-engine summary is not a source. Not opened means "unverified",
  never the site's name.
- Count origins, not domains. Five pages with the same number to the decimal
  are usually one source copied; triangulate across source types.
- Many sources repeating an unversioned number: say "repeated by N sources
  between <date> and <date>, none dated and versioned" — not a bare
  "unconfirmed".
- Conflicts are not settled by majority: the changelog decides; else the
  newest source past the fence; else show both sides as unresolved.
- META answers open with the fence: "valid for build X; sources from Y to Z;
  N of M predate build X". No superlative without version and date.
- Label each answer: documented, observed locally, or from memory with its
  cutoff.

Source order per branch, wiki and video rules, and collection traps:
[references/sources.md](references/sources.md).

## Never

- Convert a `buildid` into a marketing version.
- Treat client and dedicated server as one version: different appids,
  updated at different times.
- Cite a hosting blog as documentation.
