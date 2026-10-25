# Agent CLIs: running one as a worker, and where it loads extensions

Stable facts per CLI. Flags drift between releases: check `<cli> --help` before
relying on a row, and the linked docs when it matters. Installed versions and
when each row was last confirmed:
`bench/shared/2026-10-21-agent-cli-inventory-CLAIMS.md`.

## Contents

- Running as a worker
- Extensions: skills, plugins, hooks, MCP
- Native multi-agent
- Traps

## Running as a worker

Every CLI here runs a prompt headless and can resume that session by id, so a
host can hold a multi-turn conversation with it: one process per turn, same
session.

| CLI | Headless | Resume | Model | Read-only | Schema output |
|---|---|---|---|---|---|
| [Claude Code](https://code.claude.com/docs/en/cli-reference) | `claude -p` | `--resume <id>` | `--model` | `--permission-mode plan` | `--json-schema` |
| [Antigravity `agy`](https://antigravity.google/docs) | `agy -p` | `--conversation <id>` | `--model` | `--mode plan` | `--json-schema` |
| [opencode 2.x](https://opencode.ai/v2/docs) | `opencode run --standalone` | `-s <id>` | `-m provider/model` | `permission` deny rules | none: parse the last JSON object |
| [Copilot CLI](https://docs.github.com/en/copilot/reference/copilot-cli-reference) | `copilot -p` | `--resume <id>` | `--model` (Free plan: `auto` only) | `--excluded-tools` | none |
| [Grok Build](https://github.com/xai-org/grok-build) (`~/.grok/docs/`) | `grok -p` | `--resume` | `-m` | `--permission-mode plan` | `--json-schema` |
| [Hermes](https://hermes-agent.nousresearch.com/docs) | `hermes -z` | `--resume <id>` | `-m` | narrow `-t` toolsets | none |
| [Codex](https://developers.openai.com/codex) | `codex exec` | `codex exec resume <id>` | `-m` | `-s read-only` | `--output-schema` |
| [Cursor CLI](https://cursor.com/docs/cli/using) | `cursor-agent -p` | `--resume <id>` | `--model` | `--mode plan` or `ask` | none |
| Muse Code (`muse exec --help`) | `muse exec` | `--session-id` | `--model` | permission profile | `--output-schema` |
| [Kimi Code](https://moonshotai.github.io/kimi-code/) (`~/.kimi-code/bin/kimi`) | `kimi -p` | `-S <id>` | `-m` | none headless: `--plan` refuses `-p` | none; `--output-format stream-json` |

Kimi's `--skills-dir` replaces the discovered skill folders for one run, which
isolates a worker.

ZCode is not a worker yet. `zcode` opens the desktop app, but the app bundles a
CLI (`zcode-cli`, at `/opt/ZCode/resources/glm/zcode.cjs`). Run it as
`ELECTRON_RUN_AS_NODE=1 /opt/ZCode/zcode <path>/zcode.cjs`. It has `-p`,
`--resume <sessionId>`, `--mode plan`, `--json` and `skills list`. Two things
block `-p` from the bundle:

- it looks for `provider/zcode-builtin.json` next to `zcode.cjs`, while the
  app keeps it in `resources/config/provider/`;
- even with a copy that finds it, the run stops at "Select a model before
  sending a message". `-p` takes no model, and the default is saved by the
  CLI's TUI, which the bundle lacks (`@zcode/tui`).

Its `app-server` protocol takes a model per message, which is the remaining
way in.

A worker's exit code 0 proves nothing: agy, opencode and Copilot all exit 0 on
failed or cut runs. Judge from the event stream and a gate.

## Extensions: skills, plugins, hooks, MCP

| Tool | Global skills | Project skills | Claude Code plugins | Hooks | Trust gate |
|---|---|---|---|---|---|
| Claude Code | `~/.claude/skills`, plugins | `.claude/skills` | native | settings `hooks`, plugin `hooks/hooks.json` | — |
| Antigravity | `~/.gemini/config/skills` | `.agents/skills` | copies via `agy plugin import claude` | `.agents/hooks.json`, PascalCase events | — |
| opencode | `~/.agents/skills`, `~/.claude/skills`, `~/.config/opencode/skills` | `.agents`, `.claude`, `.opencode` | no | only through a JS plugin | — |
| Copilot CLI, desktop app, VS Code | `~/.agents/skills`, `~/.copilot/skills` | `.agents`, `.github`, `.claude` | installs Claude-format marketplaces into `~/.copilot` | `.github/hooks/` | folder trust per session |
| Grok Build | `~/.agents`, `~/.claude`, `~/.cursor`, `~/.grok` skills | `.agents`, `.claude`, `.grok` | loads every plugin installed in Claude Code | reads Claude's format and settings | `grok --trust` per folder |
| Hermes | `~/.hermes/skills`, `skills.external_dirs` | `.agents`, `.hermes`, after `hermes skills trust` | no | own `hooks:` in config, approved once | per repo |
| Codex and the ChatGPT app | `~/.agents/skills` | `.agents/skills` | installs Claude-format marketplaces | `.codex/hooks` | — |
| Cursor | `~/.agents`, `~/.cursor`, `~/.claude` skills | `.agents`, `.cursor`, `.claude` | CLI loads Claude's installed plugins | `hooks.json`, also Claude's | — |
| Kimi Code | `~/.agents/skills`, `~/.kimi-code/skills` | `.agents`, `.kimi-code` | no | `[[hooks]]` in `config.toml` | TUI asks per folder; `-p` loaded project skills without it |
| ZCode | `~/.agents/skills`, `~/.zcode/skills` | `.agents`, `.zcode` | installs Claude-format marketplaces | `~/.zcode/cli/config.json`, `hooks.enabled` | — |
| Muse Code | `~/.agents/skills`, `~/.claude/skills` | `.agents/skills` | no | — | interactive, once per folder |

`~/.agents/skills` is the one folder nearly every tool reads; `link_skills.py`
at the repo root links this marketplace's skills there.

## Native multi-agent

Read from each installed TUI's slash menu, its binary, or `codex features
list`, not only the docs: the docs list commands an account may not have, and
miss ones it does. Preview and experimental features are marked.

| Tool | Subagents | Scripted fan-out or teams | Commands |
|---|---|---|---|
| Claude Code | Agent tool, `.claude/agents/` | Workflow tool (dynamic workflows, `ultracode`); agent teams (experimental) | `/agents`, `/workflows`, `/tasks`, `/bg` |
| Antigravity | `invoke_subagent`, `.agents/agents/` | `run_workflow` (Python: `agent`, `parallel`, `pipeline`, `phase`); `/teamwork-preview` (preview, paid plans: absent from this account's menu); `/boost` (docs only, absent here) | `/agents`, `/tasks`, `/run-workflow` |
| Copilot CLI | `task`, `/subagents`, custom `/agent` | `/fleet`; `/delegate` hands off to the cloud agent | `/tasks`, `/research`, `/autopilot`, `/experimental` |
| Codex | `spawn_agent`, `resume_agent`, `close_agent` (`multi_agent`, stable, on) | `multi_agent_v2` (stable, off by default); `agent_message_board` (under development) | `codex features list` |
| Grok Build | `spawn_subagent`, `.grok/agents/` | Rhai workflows; built-in `/deep-research` | `/create-workflow` |
| Hermes | `delegate_task` | `/moa` (mixture of agents); Kanban of worker profiles | `/agents`, `/bg`, `/queue`, `/steer`, `/goal` |
| Kimi Code | `subagent` tool | `/swarm on\|off` (swarm mode) | `/goal`, `/sessions` |
| opencode | `task` with `mode: subagent` agents | none found | — |
| Cursor | subagents (docs) | none found | not read: the TUI asked to log in |
| Muse Code | yes | Workflow tool (its bundled skills drive it) | not read: trust screen |
| ZCode | yes | dynamic workflows (`--workflow-mode`, `/dwf`); `/expert` | from the bundled CLI's `--help` |

Use the native mechanism for the host's own models; use another CLI for another
vendor's quota or model family. A native subagent or workflow step can itself
call another CLI, and a host can ask another CLI to run its own workflow
headless (for example `claude -p` running `agent-fleet:deep-research`).
Per-harness subagent definitions: `agent-fleet/references/harnesses.md`.

## Traps

- A worker loads its user's global instructions, skills, MCP servers and hooks
  unless told not to. Grok loads all of Claude Code's; strip them per run
  (`fleet_worker.py` in agent-fleet shows the flags for grok, agy, opencode and
  Hermes).
- Headless write access needs a per-tool permission bypass; a guard must then
  be the CLI's own pre-tool hook, installed for the run only.
- A worker that loads crew could delegate again; crew refuses to run when
  `CREW_RUN` is set, and sets it on every worker it starts.
- Two `copilot` binaries can be on PATH: `~/.local/bin` (the CLI) shadows
  `/usr/bin/copilot` (VS Code's shim).
