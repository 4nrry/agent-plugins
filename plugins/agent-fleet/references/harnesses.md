# Tiers per harness

Where each harness defines a child agent, sets its model, and makes it
read-only. Model names and limits change with releases: list the models the
installed harness offers before choosing, and check the linked docs when a row
matters.

## What to rely on

- Every harness below runs a child with a fresh context and a model set per
  agent definition, defaulting to "inherit".
- Do not rely on choosing the model at spawn time, on nesting beyond one
  level, on more than about ten parallel children, or on structured output
  from a child. Parse the child's last JSON object and validate it yourself.

| Harness | Child agents | Model set in | Read-only child |
|---|---|---|---|
| [Claude Code](https://code.claude.com/docs/en/sub-agents) | `.claude/agents/*.md`, Agent tool | `model:` in the file, or per invocation (wins); `haiku` / `sonnet` / `inherit` | `tools:` allowlist or `disallowedTools:` |
| [Antigravity](https://antigravity.google/docs/subagents) | `.agents/agents/*.md`, `invoke_subagent` | `model:` in the file only, so one file per tier | `tools:` allowlist, empty by default |
| [opencode](https://opencode.ai/docs/agents/) | `.opencode/agents/*.md` with `mode: subagent` | `model: provider/id` in the definition | `permission:` per tool; deny `edit`, `bash`, `execute`, `task` |
| [Grok Build](https://github.com/xai-org/grok-build) | `.grok/agents/*.md`, `spawn_subagent` | spawn argument, role, persona or `[subagents.models]` | capability mode `read-only` |
| [Hermes](https://hermes-agent.nousresearch.com/docs/user-guide/features/delegation) | no files; `delegate_task` batches | `delegation.model` in config only | start the parent with a narrow `-t`; children inherit its toolsets |

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
