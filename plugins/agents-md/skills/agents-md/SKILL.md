---
name: agents-md
description: Writes, trims and audits a repository's AGENTS.md (or CLAUDE.md, GEMINI.md) — what belongs in it, what to cut, size limits per tool, and a mechanical check for missing commands, dead paths, oversize files and a CLAUDE.md that hides AGENTS.md. Use when a task mentions AGENTS.md, CLAUDE.md, GEMINI.md, .cursorrules, agent instructions, a rules token budget, an outdated or bloated instructions file, or /init.
---

# AGENTS.md

The file loads into every session, so every line costs tokens on every task,
and a long file makes the agent miss the rule that matters. Test each line:
without it, would the agent get something wrong? If not, cut it.

## Keep

- Exact commands that exist: install, run, the narrowest test, lint/typecheck, migrations.
- How to prove the work is done: the command that passes or fails.
- Traps that fail silently: a command that passes without testing anything, a required env var, config that needs a restart.
- Contracts with other repos that this code does not reveal: queue or routing key, header, ID format, exposed port.
- Conventions that depart from the language or framework default.
- Repo etiquette: base branch, branch naming, squash or not, what to run before committing.
- Architecture decisions with their reason, only where the code does not show it.
- A short map: where the 3–5 most-searched things live.
- Pointers with a trigger: "before editing X, read `<subdir>/AGENTS.md`".

## Cut

- Directory trees, endpoint lists, schema dumps, dependency lists, per-file descriptions: the agent reads the code.
- Tutorials and API docs: link them.
- Anything that changes often: versions, counts, "last updated", sprint state.
- Obvious advice ("write clean code").
- Changelog and ticket history: git has them.
- Single-tool instructions ("use MCP X first").
- Secrets, tokenized URLs, customer data.

## Form

- Short bullets under headings; dense paragraphs are followed less.
- Concrete and checkable: "run `npm test -- foo`", not "test your changes".
- Calm tone with the reason. `IMPORTANT` on one line at most: current models overapply aggressive phrasing.
- No contradictions between the root file and nested ones; the agent picks one at random.
- Human-only notes go in `<!-- block comments -->`, which Claude Code strips before loading.

## Size and placement

- Target 60–100 lines and under 6 KB; cap at 150 lines / 10 KB.
- One `AGENTS.md` for every tool. A `CLAUDE.md` or `CLAUDE.local.md` in the same folder or above hides `AGENTS.md` from Claude Code unless it imports `@AGENTS.md`.
- `@import` saves nothing: imported files load at startup too.
- Rules for one part of the code go in a nested `AGENTS.md` (nearest wins). A loose doc in `docs/` only if someone audits it against the code.
- A multi-step procedure becomes a skill; a rule that must never fail becomes a hook.
- Per-tool file names, limits and global locations: [references/tool-limits.md](references/tool-limits.md).

## Audit cheaply

1. Run the mechanical check from this skill's directory:

   ```bash
   python3 scripts/check_agents_md.py <repo>    # exit 1 when anything is flagged
   ```

   It flags oversize files, `npm run X` with no such script, cited paths that do not exist, shouting, a shadowing `CLAUDE.md`, and `GEMINI.md` bare `@file` lines Antigravity does not expand. Paths relative to another repo are expected false positives.
2. Audit against the default branch on origin, not a stale checkout: `git archive origin/<default> | tar -x -C <dir>`.
3. For facts a regex cannot reach (queues, ports, env vars, module names), give one cheap-tier agent per file the task of returning **only** false statements with `path:line`. Check each before applying it.
4. In Claude Code, `/doctor prompt-audit` finds missing commands and contradictions across files.

## Maintain

- Review the file in any PR that changes a command, port, queue or layout. A stale file is worse than none: the agent believes it.
- Add a line when the agent repeats a mistake or a review catches something it should have known.
- After changing a rule, check that behavior changed. If not, the file is too long or the sentence is ambiguous.
