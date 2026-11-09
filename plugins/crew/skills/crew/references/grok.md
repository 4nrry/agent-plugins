# crew through Grok Build

Read [delegate.md](delegate.md) first. Commands run from the crew skill's
directory (the one holding `SKILL.md`). Requires `grok` on PATH and logged in;
a version other than the tested one is a warning (Grok updates itself).

```bash
python3 scripts/crew.py delegate /path/TASK.json --backend grok
```

Use it to spend xAI quota on a slice. Never from Grok itself.

## Before the first run

**Trust the repo in Grok once:** `cd <repo> && grok --trust inspect`. Grok
loads hooks only in a folder it trusts, so crew refuses an untrusted repo.
Tell the user that trust also lets the repo's own hooks, MCP servers and
instructions load in their Grok sessions.

## The run

`grok -p --sandbox workspace --permission-mode bypassPermissions` at the repo
root, with `--tools run_terminal_cmd,read_file,search_replace,list_dir,grep,write,todo_write`
and `--no-subagents`, plus `-m` and `--reasoning-effort`.

- **Tool IDs.** `--tools` takes IDs: the shell is `run_terminal_cmd`, shown to
  the model and to hooks as `run_terminal_command`. An entry that names no tool
  makes Grok drop the whole list (every tool is offered) with a stderr warning;
  crew up to 0.15.0 passed `run_terminal_command` and hit this on 1.0.70 and
  1.0.77. The verdict now warns on that line, and on any tool the init event
  offers beyond the list.
- **The sandbox.** `workspace` lets the worker write only in the repo and temp
  dirs, enforced by the kernel. It also keeps the worker from editing
  `~/.grok/hooks`.
- **crew's hooks.** They go in a file for this run only,
  `~/.grok/hooks/crew-<run>.json`, removed at the end. Each handler acts only
  when `CREW_RUN` is this run's, so the user's other Grok sessions see a no-op.
  A file left by a killed run is inert; delete it.

## Guard and gate

- `PreToolUse`: every tool is translated to agy's names and goes through the
  same path, scope, secret and command rules. MCP tools (`server__tool`) are
  denied, since `--tools` does not remove them. So is any tool outside the list.
- `Stop`: the gate runs. While it fails, the stop is blocked with its output,
  up to `max_gate_attempts`; when it passes, the stop is blocked at most twice
  more if the final message lacks the JSON report. Grok also sends a closing
  `Stop` with no message, which is never blocked.

## Task fields

| Field | Meaning |
|---|---|
| `model` | default `grok-4.7`; `grok models` lists the others |
| `effort` | default `medium`; grok-4.7 takes `low`, `medium`, `high`, `xhigh` (1.0.77 refuses any other: "unknown effort level") |

**Long context.** Grok Build has no flag for its 500k window (the TUI's
`/context-window`). `[model."grok-4.7"]` with `context_window = 500000` in
`~/.grok/config.toml` sets it for every session, crew's included (set on this
machine since 2026-10-26): on 2026-10-25 a 268,743-token request went through
with it. The `GROK_CONFIG`
overlay drops `model.*`, so crew cannot set it per run. Before 1.0.74 Grok could
fall back to the smaller window after an idle spell or a failed request, and
compact early (its changelog, `~/.grok/CHANGELOG.md`).

## Failures only grok has

| Failure | Why it exists |
|---|---|
| refused: repo not trusted | Grok would skip the hooks silently |
| no `result` event, or `is_error` | the run was cut or failed; exit 0 says nothing |
| hooks did not load (no SessionStart) | the run had only the sandbox |

## Ask and review

`crew.py ask grok` and `review --backend grok` run in plan mode with
MCP denied and no crew hooks. `ask --web` removes every other built-in by ID
with `--disallowed-tools`, not `--tools`: Grok's X search is a backend tool
that any allowlist drops and no ID names. The worker is offered `web_search`
and `web_fetch` and still searches X (checked on 1.0.77); a tool beyond those
is a warning.
