# Tiers per harness

Where each harness defines a child agent, sets its model and effort, and
makes it read-only. Model names and limits change with releases: list the
models the installed harness offers before choosing, and check the linked docs
when a row matters.

## What to rely on

- Every harness below runs a child with a fresh context and a model set per
  agent definition, defaulting to "inherit".
- Do not rely on choosing the model at spawn time, on nesting beyond one
  level, on more than about ten parallel children, or on structured output
  from a child. Parse the child's last JSON object and validate it yourself.
- Grok Build runs up to 32 subagents at once per session and queues the rest;
  `[subagents] max_concurrent` in `config.toml` (or
  `GROK_MAX_CONCURRENT_SUBAGENTS`) changes the cap.

| Harness | Child agents | Model set in | Effort set in | Read-only child |
|---|---|---|---|---|
| [Claude Code](https://code.claude.com/docs/en/sub-agents) | `.claude/agents/*.md`, Agent tool | `model:` in the file, or per invocation (wins); `haiku` / `sonnet` / `inherit` | `effort:` in the file, Agent tool `effort`, workflow `agent(p, {effort})` | `tools:` allowlist or `disallowedTools:` |
| [Antigravity](https://antigravity.google/docs/subagents) | `.agents/agents/*.md`, `invoke_subagent` | `model:` in the file only, so one file per tier | not per child: the file has no effort key | `tools:` allowlist, empty by default |
| [opencode](https://opencode.ai/docs/agents/) | `.opencode/agents/*.md` with `mode: subagent` | `model: provider/id` in the definition | `variant:` beside the agent's own `model`; `subagent` tool `model#variant` | `permission:` per tool; deny `edit`, `bash`, `execute`, `task` |
| [Grok Build](https://github.com/xai-org/grok-build) | `.grok/agents/*.md`, `spawn_subagent` | spawn argument, role, persona or `[subagents.models]` | `effort:` in the file, or persona `reasoning_effort`; not a spawn argument | capability mode `read-only` |
| [Hermes](https://hermes-agent.nousresearch.com/docs/user-guide/features/delegation) | no files; `delegate_task` batches | `delegation.model` in config only | `delegation.reasoning_effort`, one for all children, else the parent's | start the parent with a narrow `-t`; children inherit its toolsets |

Claude Code resolves a subagent's effort as `CLAUDE_CODE_EFFORT_LEVEL` > Agent
tool `effort` > the definition's `effort` > the session level; with the env var
set, the Agent tool drops its `effort`.

Codex sets child effort in a role TOML's `model_reasoning_effort`, Copilot in
`subagents.agents.<name>.effortLevel`. Per-run effort flags for each CLI, and
tiers as model plus effort, are in crew's `scripts/backends.py`; its other
worker flags are in crew's `references/clis.md`.

## Scripted fan-out and built-in deep research

- **Claude Code**: the Workflow tool runs a JS script of `agent()` calls. An
  `agent()` without `model:` inherits. The bare `/deep-research` runs the
  unrouted built-in; this plugin ships `agent-fleet:deep-research`, routed,
  and its hook denies the bare name. Under `ultracode` fan-out is the session
  default. Resume a stopped run by run id: finished phases replay from cache.
- **Grok Build**: Rhai workflows in `.grok/workflows/`; `/deep-research` is a
  built-in one that sets no per-agent model, so route it through
  `[subagents.models]` or an edited copy.
- **Antigravity, opencode, Hermes**: no scripted fan-out; Hermes has a Kanban
  board of worker profiles.

## Isolation traps

- Grok Build loads Claude Code's plugins, skills, hooks and `CLAUDE.md`, plus
  your `~/.grok/rules/` and MCP servers, even in plan mode. A child that must
  see only its task needs those off.
- Hermes children get the parent's tools, so read-only is decided when the
  parent starts.
- Hooks differ per harness in events and JSON shape; none of them reads
  another's hook format except Grok Build, which reads Claude Code's.
