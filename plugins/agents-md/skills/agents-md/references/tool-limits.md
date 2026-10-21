# What each tool reads

Limits change with releases; check the linked docs before relying on a number.

| Tool | Reads | Limit |
|---|---|---|
| [Claude Code](https://code.claude.com/docs/en/memory) | `CLAUDE.md`; `AGENTS.md` only when no `CLAUDE.md` or `CLAUDE.local.md` exists in the folder or above | recommends under 200 lines |
| [Antigravity](https://antigravity.google/docs/rules) | `AGENTS.md`, `GEMINI.md`, `.agents/rules/`; not `CLAUDE.md`; a bare `@file` is not inlined, only `@[label](path)` | truncates each file past 24 KB; about 20k tokens for all always-on rules |
| [Codex](https://developers.openai.com/codex/guides/agents-md) | `AGENTS.override.md` or `AGENTS.md`, from the git root down to the cwd | stops concatenating at 32 KiB |

## Scope

- Claude Code searches every folder above the cwd for `AGENTS.md`; Antigravity
  and Codex stop at the git root. A shared `AGENTS.md` above several repos
  reaches those two only through a pointer in each repo's file.
- Antigravity sums the files of every repo open in the workspace. Open the
  task's repo, not the parent folder, before cutting a good file.

## Global files

- Claude Code reads only `~/.claude/CLAUDE.md`; there is no user-level `AGENTS.md`.
- Antigravity reads `~/.gemini/config/AGENTS.md` (or `GEMINI.md`).
- Keep one and generate the other from it.
