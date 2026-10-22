# Extension audit checklist

`[lint]` items are checked by `scripts/lint_extensions.py`; the rest need
judgment. Each section ends with its sources — when a source and this list
disagree, the source wins.

## Contents
- Skills: metadata, body, files, scripts
- Plugins
- Hooks
- Instructions and prompts
- Portability across harnesses
- Evaluation

## Skills: metadata

- [lint] `name`: ≤64 chars, lowercase letters, digits and hyphens, no "anthropic" or "claude", matches the directory.
- [lint] `description`: present, ≤1,024 chars, no XML tags.
- [lint] Description in third person ("Extracts…", not "I can…" or "You can…").
- [lint] Frontmatter is valid strict YAML: quote a value that contains `: ` or ` #`. Claude Code reads it anyway; Copilot CLI silently drops the skill.
- Description says what the skill does *and* when to use it, with the terms a user would type. Key use case first: Claude Code cuts description plus `when_to_use` at 1,536 chars.
- Name is specific (gerund or noun phrase), consistent with sibling skills; not `helper`, `utils`, `tools`.
- Outside Claude Code only `name`, `description`, `license`, `compatibility`, `metadata` and `allowed-tools` are accepted; other keys are a hard error on claude.ai and the Skills API.

## Skills: body

- [lint] Body under 500 lines; split into referenced files before that.
- [lint] No marketing words (powerful, comprehensive, seamless, cutting-edge…).
- [lint] Written in English when the repo targets English.
- [lint] No dated facts in the body: tested versions, ISO dates, prices. Put them in records or an "old patterns" section.
- Every paragraph earns its tokens: nothing the model already knows; no padding, no caveat tables that do not change what the agent does.
- One default per decision, with an escape hatch — not a menu of options.
- Freedom matches fragility: exact commands for fragile operations, heuristics where many paths work.
- One term per concept throughout.
- Multi-step work has a copyable checklist and a validate → fix → repeat loop.
- Examples are concrete input/output pairs where format matters.

## Skills: files and scripts

- [lint] Relative links resolve; references are one level deep from SKILL.md.
- [lint] Reference files over 100 lines start with a table of contents.
- [lint] No `${CLAUDE_PLUGIN_ROOT}` in skill bodies; use paths relative to the skill directory (portable) or `${CLAUDE_SKILL_DIR}` (Claude Code only).
- [lint] Forward slashes only.
- Intent is explicit: "run `scripts/x.py`" vs "read `scripts/x.py`".
- Scripts handle their own errors with actionable messages; constants are justified in a comment.
- Required packages are named and verified, not assumed.
- Deterministic work (validation, parsing, checks) is a script, not prose.
- MCP tools are named fully qualified (`Server:tool`).

Sources: [Skill authoring best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices),
[Agent Skills spec](https://agentskills.io/specification), [Claude Code skills](https://code.claude.com/docs/en/skills).

## Plugins

- [lint] New components use `skills/`, not `commands/`.
- `claude plugin validate --strict` passes (manifest, kebab-case `name`, `version`, `description`, `author`, paths inside the root).
- Name does not pass as Anthropic's (`claude-*`, `anthropic-*`, `official` beside either).
- `version` is bumped with every behavior change; users are pinned to it.
- State goes to `${CLAUDE_PLUGIN_DATA}`, never `${CLAUDE_PLUGIN_ROOT}` (replaced on update).
- No `CLAUDE.md` at the plugin root (not loaded); instructions live in skills.
- Secrets come from `userConfig` with `sensitive: true`, not from files in the plugin.

Sources: [Plugin manifest reference](https://code.claude.com/docs/en/plugins-reference).

## Hooks

- A hook exists only for what must happen every time; judgment stays in skill text.
- [lint] JSON output is built with an encoder (`jq`, a JSON library), not string concatenation.
- Paths in shell-form commands are quoted (`"${CLAUDE_PLUGIN_ROOT}"/…`), or the hook uses exec form with `args`.
- Exit codes are deliberate: a broken check fails open unless blocking is the point, and says why on stderr.
- Fits its timeout: `UserPromptSubmit` defaults to 30 s, `SessionEnd` shares 1.5 s.
- At most one hook rewrites a given tool's input; parallel hooks finish in any order.
- Input from the tool call and the web is untrusted: never `eval` it, never splice it unquoted into a shell.
- A `PostToolUse` hook cannot undo; guards belong in `PreToolUse`.
- Tested by piping sample JSON into the script and checking stdout and exit code.

Sources: [Hooks guide](https://code.claude.com/docs/en/hooks-guide), [Hooks reference](https://code.claude.com/docs/en/hooks).

## Instructions and prompts

- Few, non-contradictory rules. Instruction-following degrades as rules pile up (one 2026 preprint: near zero full compliance at 80 simultaneous rules); contradictions cost more than omissions.
- Mixed content is sectioned with one delimiter style (XML tags or headings), not both.
- Long reference material sits above the question or task.
- Reasoning is configured, not prompted: effort/thinking settings, not "think step by step" boilerplate.
- Runtime instructions that tell an agent to stop, ask or confirm say exactly when.

Sources: [Claude prompting best practices](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices),
[Effective context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents),
[OpenAI GPT-5 prompting guide](https://developers.openai.com/cookbook/examples/gpt-5/gpt-5_prompting_guide),
[Gemini prompting strategies](https://ai.google.dev/gemini-api/docs/prompting-strategies),
[arXiv 2607.19257](https://arxiv.org/abs/2607.19257).

## Portability across harnesses

- The skill folder works when copied alone into `.agents/skills/`: scripts and references inside it, relative paths.
- Harness-specific steps (tool names, slash commands, model aliases) live in a reference file, not the main body.
- Model choices are named as tiers (cheap, mid, orchestrator) with a per-harness map.
- Hooks are treated as harness-specific: each harness has its own events and JSON shapes.

## Evaluation

- At least three realistic cases per skill, including one that should *not* trigger it.
- Scored against a no-extension baseline; a case that passes both ways proves nothing.
- Several prompt variants per case: format and wording swing scores, more on small models.
- Deterministic graders (regex, tool used, file exists) before model judges; judges only for short outputs with concrete pass/fail rubrics.
- Re-run after each model release and each platform update.

Sources: [Plugin evals](https://code.claude.com/docs/en/plugin-evals), [arXiv 2510.05152](https://arxiv.org/abs/2510.05152).
