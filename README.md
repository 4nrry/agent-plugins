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

In Claude Desktop, paste `https://github.com/4nrry/agent-plugins.git` into the
**Add marketplace** dialog.

## Other agent tools

Codex (and the ChatGPT app), GitHub Copilot, Grok Build, Cursor, Kimi Code,
ZCode, opencode, Muse Code, Hermes and Antigravity read plain skill folders.
`scripts/link_skills.py` symlinks each skill into them, pointing at Claude
Code's marketplace clone, so updating the marketplace updates every tool:

```
just link-skills global                          # agent-fleet, crew, media-agent (GLOBAL in the script)
just link-skills project ~/code/app mobile-agent  # into the repo's .agents/skills, git-excluded
just link-skills status ~/code/app
```

| Tool | Global folder | Project folder |
|---|---|---|
| Codex and the ChatGPT app, Copilot CLI, Cursor, Kimi Code, ZCode, opencode | `~/.agents/skills` | `.agents/skills` |
| Grok Build, Muse Code | `~/.agents/skills` | `.agents/skills`, once the folder is trusted |
| Hermes | `~/.agents/skills` once listed in `skills.external_dirs` | `.agents/skills`, after `hermes skills trust` |
| Antigravity | `~/.gemini/config/skills` | `.agents/skills` |
| Claude Code | the plugins | the plugins, per project in `.claude/settings.local.json` |

Hooks and MCP servers do not travel with a linked skill. For tools without
Claude-format plugins, `adapters/<tool>/` holds a bridge that `global` links
into the tool's own folder; it runs the global plugins' `hooks/hooks.json` and
`mcp.json` from the marketplace clone, so there is no second copy:

| Tool | Hooks | MCP servers |
|---|---|---|
| opencode | `adapters/opencode/4nrry-bridge.js`, linked into `~/.config/opencode/plugins/` | the same bridge |
| Hermes | `adapters/hermes/4nrry-bridge/`, linked into `~/.hermes/plugins/`; once: `hermes plugins enable 4nrry-bridge` | once: `hermes mcp add kinocut --command python3 --args ~/.claude/plugins/marketplaces/4nrry/adapters/mcp_launch.py media-agent kinocut` |
| Kimi Code | once, in `~/.kimi-code/config.toml`: a `[[hooks]]` entry each for `UserPromptSubmit` and `PreToolUse` running `python3 ~/.claude/plugins/marketplaces/4nrry/adapters/claude_hooks.py <event>` | once, in `~/.kimi-code/mcp.json`: `"kinocut": {"command": "python3", "args": ["~/.claude/plugins/marketplaces/4nrry/adapters/mcp_launch.py", "media-agent", "kinocut"]}` (absolute path) |
| ZCode | once, in `~/.zcode/cli/config.json` under `hooks.events`: a `process` entry each for `UserPromptSubmit` and `PreToolUse`, `"command": "python3", "args": ["~/.claude/plugins/marketplaces/4nrry/adapters/claude_hooks.py", "<event>"]` | once, in the same file: `mcp.servers.kinocut = {"type": "stdio", "command": "python3", "args": ["~/.claude/plugins/marketplaces/4nrry/adapters/mcp_launch.py", "media-agent", "kinocut"]}` |
| Muse Code | once, in `~/.config/muse/settings.json` under `hooks`: a `command` entry each for `UserPromptSubmit` and `PreToolUse` running `python3 ~/.claude/plugins/marketplaces/4nrry/adapters/claude_hooks.py <event>` | once, in the same file: `mcpServers.kinocut = {"type": "stdio", "command": "python3", "args": ["~/.claude/plugins/marketplaces/4nrry/adapters/mcp_launch.py", "media-agent", "kinocut"], "mode": "optional"}` |

`adapters/mcp_launch.py PLUGIN SERVER` starts a server from the plugin's
`mcp.json`, so the version pin lives in one place. `adapters/claude_hooks.py EVENT`
runs every matching hook for tools whose hooks already speak Claude Code's
contract (stdin JSON, exit 2 blocks, stdout becomes context), as Kimi's, ZCode's
and Muse's do; it maps their tool names (`bash`, `exec_command`) to
Claude's. Both bridges do nothing
inside a crew worker run (`CREW_RUN`).

Copilot, Codex and Cursor install the global plugins themselves: each ships an
Agent Plugins `plugin.json`. Copilot can load them live from Claude Code's
marketplace clone: `copilot plugin marketplace add ~/.claude/plugins/marketplaces/4nrry`. Grok and Cursor also
load the Claude Code plugins themselves, hooks included. Codex can install this
marketplace too; do not, or each skill loads twice. ZCode and Muse can
install them too (ZCode with hooks, Muse without); do not, for the same reason. crew is linked too: a
crew run sets `CREW_RUN`, and crew refuses to start a worker inside one.

## Plugins

| Plugin | What it is |
|---|---|
| [agent-fleet](plugins/agent-fleet/) | Rules for multi-agent work — model routing per phase, fan-out sizing, output schemas, and citation verification. Two hooks, because the prose alone measurably did not fire. |
| [agents-md](plugins/agents-md/) | Write, slim and audit a repo's AGENTS.md: what goes in, what comes out, per-tool limits (Claude Code, Antigravity, Codex), and a stdlib checker for missing scripts, dead paths, oversize files and the CLAUDE.md that hides AGENTS.md from Claude Code. |
| [crew](plugins/crew/) | Another vendor's agent CLI as an isolated subagent, from any host: ask a read-only question or hold a multi-turn conversation (agy, opencode, Codex, Grok, Hermes, Copilot, Cursor, Muse, Kimi, or Claude Code from another host), get a second opinion on a diff, or delegate one coding slice to agy, opencode, Copilot, Codex, Grok or Cursor under the worker CLI's own hooks and a mechanical gate. Tiers (cheap, mid, top) map to a model and effort per backend. The verdict never reads the CLI's exit 0 as success. |
| [extension-audit](plugins/extension-audit/) | Audit skills, plugins and hooks against Anthropic's authoring guidance and current prompting research: a sourced checklist for judgment calls and a stdlib linter for the mechanical ones, which `just check` runs over this repo. |
| [game-facts](plugins/game-facts/) | Pins the installed game's version before the agent answers from training memory. A UserPromptSubmit hook reads Steam appmanifests and injects appid, buildid and update date — so the version never has to be typed into the prompt. |
| [homelab](plugins/homelab/) | Software you maintain yourself on a Linux box, where the official docs stop: a Palworld dedicated server (the config it erases on shutdown), WireGuard through NetworkManager (the IPv6 leak that passes the IP test), and tarball installs (one versioned layout, and why a self-updating app must not live in /opt). Machine state stays out of the repo. |
| [media-agent](plugins/media-agent/) | Media production by an agent on a machine with an 8 GB GPU and commercial licensing, one skill per modality with rules that hold for any model: image and video generation, image retouching, voice-over at -16 LUFS, music and sound with per-item licenses, video composed as code, editing finished video, and a 3D product turntable. One hook warns where vipsthumbnail -o really writes. |
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
script advertising `--self-test` passes it, and the
[extension-audit](plugins/extension-audit/) linter reports no errors (its
warnings are listed, not fatal). CI runs the same one command.

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
