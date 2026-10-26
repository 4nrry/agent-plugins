# crew through Claude Code

Read [delegate.md](delegate.md) first. Commands run from the crew skill's
directory (the one holding `SKILL.md`). Requires `claude` on PATH and logged
in; a version other than the tested one is a warning.

```bash
python3 scripts/crew.py delegate /path/TASK.json --backend claude
```

Use it to spend Claude quota on a slice from another host (Codex, Grok, agy,
opencode). Never from Claude Code itself: crew refuses when `CLAUDECODE` is
set, and Claude's own subagents do the same job there.

## Before the first run

Tell the user: **no OS sandbox.** Claude Code's sandbox does not start on this
machine (bubblewrap: "nested userns is capability-restricted"), so crew's hooks
are the only limit on Bash. `--restricted` still confines the file tools.

## The run

`claude -p --restricted --settings <run dir>/claude-settings.json --tools
Bash,Read,Edit,Write,Glob,Grep,TodoWrite --strict-mcp-config
--disable-slash-commands --permission-mode acceptEdits --model <model>`, at
the repo root, plus `--effort` with `"effort"` in the task.

- **`--restricted`.** The user's, project's and local settings files are
  skipped, so their hooks and plugins do not load; `--settings` does. File
  tools stay inside the repo, and writes to `.claude/` settings and `.git/` are
  refused even when a hook allows them.
- **Bash.** Headless, Bash runs only when a hook approves it, so crew's
  PreToolUse prints an explicit allow for every call its rules pass.
- **Leftover.** A refused write can leave an empty `.claude/.cc-writes` in the
  repo; crew removes it, and `.claude/`, when the run created them.

## Guard and gate

- `PreToolUse`: `Read`, `Glob`, `Grep`, `Write`, `Edit` and `Bash` are
  translated to agy's names and go through the same path, scope, secret and
  command rules. Writes into `.claude/` and MCP tools are denied; so is any
  tool outside the list.
- `Stop`: the gate runs. While it fails, the stop is blocked with its output,
  up to `max_gate_attempts`; when it passes, the stop is blocked at most twice
  more if the final message lacks the JSON report.
- A hook that exits 2 blocks the call: an unknown event or a crash before the
  guard answers denies rather than allows.

## Task fields

| Field | Meaning |
|---|---|
| `model` | default `sonnet`; `haiku`, `opus` or a full model ID |
| `effort` | `low` to `max` |

## Failures only claude has

| Failure | Why it exists |
|---|---|
| refused: the host is Claude Code | its own subagents do the same |
| no `result` object, or `is_error` | the run was cut or failed; exit 0 says nothing |
| hooks did not load (no SessionStart) | the run had only `--restricted` |

## Review

`crew.py review --backend claude` runs through `ask`, read-only in plan mode,
with no crew hooks.
