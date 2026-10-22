# Effort per subagent and per worker run, 2026-10-21 — claims

**Notes, not run records.** How reasoning effort is set for one worker run
(a host launching the CLI) and for the tool's own subagents, on the author's
machine (Kubuntu, x86-64) on 2026-10-21. Every row was checked against the
installed binary, not docs alone. No model turn was spent: probes were
`--help`, offline listings, strings in the binary, and slash menus read in a
pseudo-terminal without pressing Enter on a prompt.

| Tool | Version | Per-run effort (worker) | Subagent-definition effort | Values | Confirmed by |
|---|---|---|---|---|---|
| Claude Code | 2.1.307 | `claude -p --effort <l>`; env `CLAUDE_CODE_EFFORT_LEVEL`; `--settings '{"effortLevel":…}'` | `effort:` in `.claude/agents/*.md` and `--agents` JSON; Agent tool `effort` per call; workflow `agent(p, {effort})`; skill `effort:` | `low medium high xhigh max`; settings keys take `low`–`xhigh` only; capped per model | help; binary (`Agent` input schema, `opts.effort`, settings schema, `CLAUDE_CODE_EFFORT_LEVEL` handler); docs sub-agents, model-config, workflows |
| Antigravity `agy` | 1.4.4 | `--effort <l>`, or a slug with the level in it (`gemini-3.8-flash-low`) | none: agent frontmatter has `model` (tier: `flash`, `pro`, `inherit`), no effort key | flag: `low medium high xhigh max`; models offer `low medium high` (`gpt-oss-120b` medium only) | help; `agy models`; `agy -p /model --effort low` resolved to `gemini-3.8-flash-low` with no turn; changelog; YAML tags in the binary |
| Codex | 0.163.0 | `-c model_reasoning_effort=<l>`; `-p <profile>`; `plan_mode_reasoning_effort` for plan mode | role TOML (`.codex/agents/`, or `[agents.<name>] config_file`) with `model_reasoning_effort`; `spawn_agent` takes `reasoning_effort`, but forked children inherit and reject it | per model, from `codex debug models`: `low medium high xhigh max`, plus `ultra` on `gpt-5.6-terra` | help; `codex debug models`; `codex debug prompt-input` (spawn rules); built-in `explorer.toml`/`awaiter.toml` set `model_reasoning_effort = "low"` |
| opencode | 2.1.2 | `-m provider/model#variant` | agent config `variant` (only with the agent's own `model`); `subagent` tool `model` accepts `provider/model#variant` | per model, from `GET /api/model` `variants`: e.g. `low high max`, `low medium high xhigh max`, `none minimal low medium high xhigh`; several free models have none | help; `opencode api --standalone GET /api/model`; agent and tool schemas in the binary |
| Grok Build | 1.0.62 | `--reasoning-effort <l>` (alias `--effort`); `GROK_CONFIG='{"models":{"default_reasoning_effort":…}}'` | `effort` in agent `.md` frontmatter; persona `reasoning_effort`; `[subagents.models]` sets model only; `spawn_subagent` has no effort argument | `/effort` on `grok-4.7`: `low medium high xhigh` | help; `~/.grok/docs`; `AgentDefinition` fields and `spawn_subagent` input in the binary; TUI `/effort` |
| Copilot CLI | 1.0.102 | `--reasoning-effort <l>` | `subagents.agents.<name>.effortLevel` in settings (or `inherit`), set by `/subagents`; `.agent.md` frontmatter has `model`, no effort | `none minimal low medium high xhigh max` | help; `copilot help config`; TUI `/subagents`; docs custom-agents-configuration |
| Cursor CLI | 2026.10.19-6bbf2c4 | in the model: slug suffix (`grok-4.7-low`) or `'model[effort=high]'` | none: subagent frontmatter keys are `name description model force-default-model readonly background tools` | per model, from `cursor-agent models` | help; `cursor-agent models`; frontmatter parser in the bundle |
| Hermes | 0.22.4 | `--reasoning <l>` (with `-z` or `chat`); `agent.reasoning_effort`, per model `agent.reasoning_overrides` | one global `delegation.reasoning_effort` for all children, else the parent's; `delegate_task` has no effort field | `none minimal low medium high xhigh max ultra` | help; source `tools/delegate_tool.py`, `delegate_tool_config.py`, `hermes_constants.py`; TUI `/reasoning` |
| Muse Code | 1.4.11 | `--reasoning-effort <l>` (alias `--effort`) on `muse` and `muse exec`; `reasoningEffort` per turn over `muse serve` | not established | `none minimal low medium high xhigh max ultra`; `muse model-profile show <m> --effort <l>` shows what a tier resolves to | help; `muse model-profile`; `muse schema generate-json-schema` |
| Kimi Code CLI | 2.3.0 | no flag: `[thinking] effort` in `config.toml`; env `KIMI_MODEL_THINKING_EFFORT` only for a model defined by `KIMI_MODEL_*` env | none per agent: agent frontmatter keys are `name description whenToUse override tools disallowedTools subagents`; all subagents use `[secondary_model]` and its `default_effort` (env `KIMI_SECONDARY_EFFORT`) | per model `support_efforts`: `low high max` on K3 | help; config schema and agent parser in the binary; TUI `/effort` (alias `/thinking`) |

## Claude Code precedence

For a subagent: `CLAUDE_CODE_EFFORT_LEVEL` > Agent tool `effort` (per call;
kept on resume) > the definition's `effort` > the session level. The Agent
tool drops its `effort` input entirely while the env var is set, and ignores it
for `subagent_type: "fork"`. A `maxEffortLevel` setting or an organization cap
still applies, and a level the model lacks falls to the highest one below it.
A workflow `agent()` without `opts.effort` inherits the session level.
Behind a feature flag the Agent tool also accepts `lower`/`higher`, one step
from what the agent would otherwise run at.

## Not established

- Muse subagent definitions: no effort key found in the binary, and the TUI
  could not be opened without logging in.
- Whether agy's agent `model` accepts a full slug with the level in it, and
  whether Cursor's bracket override works in a subagent's `model`.
- Codex did not reject `-c model_reasoning_effort=bogus` in `debug
  prompt-input`; where an invalid value fails was not tested.
- Copilot on the Free plan runs `auto` only; whether `--reasoning-effort`
  changes anything there was not tested.
