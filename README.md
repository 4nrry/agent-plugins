# 4nrry's agent plugins

Plugins and skills for AI agents. The skills follow the
[Agent Skills](https://agentskills.io) open standard, so their bodies and
bundled scripts are portable across tools that speak it. The packaging in this
repo — hooks included — targets
[Claude Code](https://code.claude.com/docs/en/plugins), which consumes it as a
plugin marketplace; other formats may join as the collection grows.

## Install (Claude Code)

Add the marketplace, then install a plugin:

```
/plugin marketplace add 4nrry/agent-plugins
/plugin install agent-fleet@4nrry
```

Or paste `4nrry/agent-plugins` into the Claude Desktop **Add marketplace** dialog.

## Plugins

| Plugin | What it is |
|---|---|
| [agent-fleet](plugins/agent-fleet/) | Rules for multi-agent work — model routing per phase, fan-out sizing, output schemas, and citation verification. Two hooks, because the prose alone measurably did not fire. |
| [game-facts](plugins/game-facts/) | Pins the installed game's version before the agent answers from training memory. A UserPromptSubmit hook reads Steam appmanifests and injects appid, buildid and update date — so the version never has to be typed into the prompt. |
| [homelab](plugins/homelab/) | Software you maintain yourself on a Linux box, where the official docs stop. A Palworld dedicated server (the config the server erases on shutdown), WireGuard through NetworkManager (the IPv6 leak that passes the IP test), and tarball installs (one versioned layout, and why a self-updating app must not live in /opt). Machine state stays out of the repo. |
| [mobile-agent](plugins/mobile-agent/) | What breaks silently in a mobile app: the device layer (adb, emulator, UI dumps) and the bundler layer (Expo, Metro, prebuild). Six narrow PreToolUse guards that warn and never block. |

Each plugin's own README carries its components, its measurements, and what
those measurements do not establish.

## Benchmarks

Improvement claims about plugins in this repo are comparisons between run
records committed under `bench/plugins/<plugin>/results/`, collected per
[`bench/PROTOCOL.md`](bench/PROTOCOL.md) — per-agent token splits, resolved
model IDs, paired arms with hash-checked prompts, and outcomes tagged by
source (script measurement vs orchestrator assertion). A claim without
records is marketing and does not belong here.

Records collected before that protocol existed, or by a foreign harness, are
published as raw output with their hashes and are labeled **imported** in the
first paragraph of their claims file, together with every field they lack and
every claim that lack forbids.

Findings that belong to no single plugin — a fact about model routing or
harness behaviour that any plugin would reuse — go in
[`bench/shared/`](bench/shared/).

## Repository checks

```
just check
```

Runs [`bench/validate.py`](bench/validate.py): manifests carry no duplicated
metadata, every hook command points at an executable file, every run record
conforms to [`bench/schema/run.schema.json`](bench/schema/run.schema.json),
every `eval_ref` resolves *and* hashes to the `eval_sha256` beside it, every
`bench/` path cited in a plugin description exists, shellcheck passes, and every
script advertising `--self-test` passes it. CI runs the same one command.

## Layout

```
.claude-plugin/marketplace.json     entries are {name, source}; plugin.json is
                                    the single authority for plugin metadata
plugins/<plugin>/                   the installable plugin, with its own README
bench/PROTOCOL.md  validate.py      how records are collected, and the checker
bench/schema/                       run record + eval file shapes
bench/shared/                       findings belonging to no single plugin
bench/plugins/<plugin>/             evals, results and scripts for that plugin
```

## Licence

MIT — see [LICENSE](LICENSE).
