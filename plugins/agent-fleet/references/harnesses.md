# Applying the rules in each harness

The rules in `SKILL.md` name tiers, not models: a cheap tier for long tool
loops (search, fetch, extract), a mid tier for the adversarial pass, and the
orchestrator for scope and synthesis. This page maps those words onto each
harness. Facts come from each vendor's official docs and the installed CLIs,
read 2026-10-21; they move with every release, so re-read the linked page
before relying on a row.

## Common ground

What every harness below supports, so a rule may rely on it:

- A child agent with a fresh context that returns only its result.
- A model chosen per agent definition, with "inherit the parent" as default.
- Tool or permission scoping per definition, so a detector can be given a
  toolset with no write tool.

What not to rely on:

- Choosing the model at spawn time: Claude Code and Grok Build allow it;
  Antigravity, opencode and Hermes set it in a file or config only.
- Children nesting more than one level: Grok Build and Hermes stop at one.
- More than about 10 children at once: Hermes defaults to 10, and a batch over
  its limit is an error, not a queue.
- Structured output from a child: documented only for Hermes `delegate_task`
  and Grok Build workflows. Elsewhere, parse the child's last JSON object and
  validate it yourself.
- A built-in deep-research command: only Claude Code and Grok Build have one.

Any harness with a shell can also put the cheap-tier phases on another CLI
with `scripts/fleet_worker.py`; see the README's routing table.

## Claude Code

[Sub-agents](https://code.claude.com/docs/en/sub-agents) are
`.claude/agents/*.md` (or a plugin's `agents/`), spawned with the Agent tool.

| | |
|---|---|
| Tiers | cheap `haiku`, mid `sonnet`, top: the session model |
| Model | `model:` in the agent file, or the per-invocation `model` parameter, which wins |
| Read-only child | `tools:` allowlist or `disallowedTools:` |
| Concurrency | 20 by default (`CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS`) |
| Scripted fan-out | the Workflow tool: a JS script of `agent()`, `parallel()`, `pipeline()` calls |

**Predefined workflows inherit by default.** An `agent()` call without
`model:` runs on the session model, so a top-tier session pays top tier once
per agent. Before dispatching one, open its script and look for `model:` on
the `agent()` calls. In the one measured failure, a ~97-agent run reached its
verification fan-out with everything inheriting the top model while these
rules sat loaded in context, because nobody had read the script. Caught late,
the fix is cheap: stop the run and resume it by run id with edited overrides;
the unchanged prefix replays from cache, so the phases already paid for are
kept, not repaid.

**`/deep-research`.** The bare name dispatches the built-in workflow, with no
routing. This plugin ships a routed fork, `agent-fleet:deep-research`: search
and fetch on `haiku`, the 3-vote verify on `sonnet`, scope and synthesis on
the session model. The plugin's routing hook denies the bare name for that
reason.

**`ultracode`.** Under it the fan-out stops being a decision and becomes the
session default, because Claude orchestrates dynamic workflows for
substantive tasks on its own. A dynamic workflow holds the loop and the
intermediate results in the script, and only the final answer reaches the
context, so the schema has to be right before the run.

## Antigravity (IDE, App and `agy`)

[Subagents](https://antigravity.google/docs/subagents) are
`.agents/agents/<name>.md` (workspace) or `~/.gemini/config/agents/`, spawned
with `invoke_subagent`.

| | |
|---|---|
| Tiers | cheap `flash`, mid: Argon (see below), top: the session model |
| Model | `model:` in the agent file only: `inherit`, `flash` or `pro` per the docs |
| Read-only child | `tools:` is an explicit allowlist and defaults to empty; a misspelled name may hang the child |
| Concurrency | not documented; nesting up to 10 levels |
| Scripted fan-out | none documented; `/teamwork-preview` and `/boost` are agent teams, not scripts |

**The documented model values are behind the lineup.** The docs list `pro`,
but `agy models` (1.4.4) offers Gemini 3.8 Flash and Gemini 4 Argon, plus
Claude Sonnet/Opus 5.5 and GPT-OSS. Whether `pro` now means Argon, or `argon`
or a full slug is accepted, is untested. Since the model cannot be picked at
spawn time, one agent file per tier is the way to route.

The Claude models in agy share one weekly quota, so they make a poor default
for a fan-out.

## opencode

[Agents](https://opencode.ai/docs/agents/) are `.opencode/agents/*.md` or
`~/.config/opencode/agents/`, or an `agent` object in `opencode.json`, with
`mode: subagent`; the parent spawns them through its task tool.

| | |
|---|---|
| Tiers | any `provider/model`; free Zen models for the cheap tier (see the README for their data terms) |
| Model | `model:` in the agent definition; unset means the invoking agent's model |
| Read-only child | `permission:` per tool (`edit`, `bash`, `webfetch`, ...: `allow`/`ask`/`deny`). In 2.1.x also deny `execute`, a JS sandbox with `fetch()` |
| Concurrency | not documented |
| Scripted fan-out | none built in |

Mind the free models' windows: several are 200k, which holds one page but not
a search loop that fetches twenty.

## Grok Build

[Subagents](https://github.com/xai-org/grok-build) are `.grok/agents/*.md` or
`~/.grok/agents/`, spawned with `spawn_subagent`.

| | |
|---|---|
| Tiers | check `grok models`; the model is set per type, per role or at spawn |
| Model | spawn-time argument, then role, persona, `[subagents.models.<type>]`, then the parent |
| Read-only child | capability modes `read-only`, `read-write`, `execute`, `all`, by agent type or role |
| Concurrency | `subagents.max_concurrent`; nesting depth 1 |
| Scripted fan-out | Rhai workflows in `.grok/workflows/*.rhai`, with `agent()`, `parallel()` and `output_schema` |

**`/deep-research`** runs a built-in Rhai workflow in the background: plan,
parallel read-only researchers, a verifier per claim, a cited report. Its
script sets no per-agent model, so route it through `[subagents.models]` or a
saved, edited copy. Same rule as Claude Code: read the script before trusting
its routing.

Grok also reads Claude Code's plugins, skills, hooks and `CLAUDE.md`, and
your own `~/.grok/rules/` and MCP servers load even in plan mode. A child that
must see only its task needs those turned off explicitly.

## Hermes Agent

[Delegation](https://hermes-agent.nousresearch.com/docs/user-guide/features/delegation)
has no agent files: `delegate_task` takes a `tasks` array and runs it as one
parallel batch.

| | |
|---|---|
| Tiers | cheap: `delegation.model` in `config.yaml`; a second tier needs a Kanban profile with its own `--model` |
| Model | config only; the docs say there is no per-call model parameter |
| Read-only child | no per-task toolsets; children inherit the parent's, minus a fixed blocklist |
| Concurrency | `max_concurrent_children`, 10 by default; nesting depth 1 |
| Structured output | per-task `output_schema`, one correction retry, `schema_valid` in the result |

Because a child gets the parent's tools, structural read-only means starting
the parent with a narrow `-t` (for example `-t web`), not asking the child.
