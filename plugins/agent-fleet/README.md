# agent-fleet

Rules for multi-agent work: model routing per phase, fan-out sizing, closed
output schemas, and verifying what agents return.

```
/plugin install agent-fleet@4nrry
```

The skill lives in `skills/agent-fleet/` and the plugin ships an Agent Plugins
`plugin.json` at its root, so Copilot, Codex and Cursor can install it; other
harnesses get the skill folder through the repository's
[`scripts/link_skills.py`](https://github.com/4nrry/agent-plugins/blob/main/scripts/link_skills.py). The hooks
and the workflow are Claude Code only, and so is the plugin as a whole in
practice: claude.ai chat and Cowork run neither hooks nor the Workflow tool,
and `fleet_worker.py` needs local CLIs. There the skill is just its text, and
its description alone rarely loads it (see "Why hooks"). Paths below are
relative to the skill folder, except `hooks/` and `workflows/` at the plugin
root.

| Component | Path | Does |
|---|---|---|
| Skill | `SKILL.md` | The rules, in tiers rather than model names |
| Harness map | `references/harnesses.md` | Tiers, model setting and read-only children per harness |
| CLI workers | `references/cli-workers.md`, `scripts/fleet_worker.py` | Search and extract on another CLI through crew's `ask --web --schema`, read-only; needs the crew plugin installed |
| Verifier | `scripts/verify_citations.py` | Fetches each cited URL and string-checks the quote, from a markdown report or a JSON claims file (`--claims`) |
| YouTube captions | `scripts/yt_captions.py` | Caption text of a public video through yt-dlp when installed; exit 3 when it is not, never installs |
| Workflow | `workflows/deep-research.js` | Claude Code's built-in deep research with per-phase `model:` and `effort:` overrides, returning its confirmed quotes for `--claims` |
| Injection hook | `hooks/inject.sh` | `UserPromptSubmit`: loads the skill when the prompt names a fan-out (`ultracode`, deep research, dynamic workflow, `/dwf`, `/fleet`), asks for several subagents at once, or asks for "pesquisa" from many sources. In Claude Code, the whole skill once per session, then a short pointer to it; `SessionStart` after a compaction or `/clear` runs `inject.sh --forget`, so the next match loads it whole again. Through the bridges for other harnesses, the whole skill on every match |
| Routing hook | `hooks/check-routing.sh` | `PreToolUse` on `Workflow`: denies once a script with fewer `model:` overrides than `agent()` calls, once any other workflow invoked by name (its script cannot be read from the call), and the bare built-in name always. The count is textual: `model:` anywhere outside a `//` comment counts, a string included |

## What it runs, sends and fetches

- `hooks/inject.sh` reads every prompt, on this machine only, and prints the
  skill when its patterns match. Where `${CLAUDE_PLUGIN_DATA}` is set it
  writes one empty marker file per session under `injected/` there and
  deletes those older than 7 days. `hooks/check-routing.sh` reads each
  `Workflow` call and writes one empty marker file per script or workflow
  name it has denied, in `${CLAUDE_PLUGIN_DATA}` (or
  `~/.claude/plugins/data/agent-fleet-routing`).
  Both need `jq`, and the routing hook `sha256sum`; without them they do
  nothing and say so on stderr.
- `fleet_worker.py` sends the question, the search angles and the page URLs to
  the provider of each CLI it is told to use, through crew: xAI (grok), Google
  (agy), OpenAI (codex), Anthropic (claude), opencode's Zen, or the provider
  hermes is set to. It runs only when the agent calls it; the skill says to
  ask first.
- `verify_citations.py` fetches the URLs a report cites, public http(s)
  addresses only, and sends nothing else. `yt_captions.py` runs `yt-dlp`
  against YouTube when it is installed.
- The workflow runs Claude Code subagents with web search and fetch.

## Why hooks

The skill's description fired on 2 of 30 should-trigger runs, and no rewrite
helped, so a substring hook loads it instead. The routing rule was loaded
during a ~97-agent run that still inherited the top model, so a hook checks
for it at dispatch.

## Evidence

Records and claims live in [`bench/plugins/agent-fleet/`](https://github.com/4nrry/agent-plugins/tree/main/bench/plugins/agent-fleet):
the trigger eval, the hook-grep batch, the breadth-tier batch, and the
fleet-worker smoke notes. The rules in the skill come from earlier paired runs
that predate the bench protocol; read those as design notes.

`workflows/deep-research.js` is Claude Code's built-in script plus `model:` and
`effort:` overrides, a `confirmed` list of quotes in its result and a corrected
Fetch phase text; its header names the builds it was taken from and compared
with, and says how to rebase it when the built-in changes.
