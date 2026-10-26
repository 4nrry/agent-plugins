# crew through Cursor CLI

Read [delegate.md](delegate.md) first. Commands run from the crew skill's
directory (the one holding `SKILL.md`). Requires `cursor-agent` on PATH and
logged in; a version other than the tested one is a warning.

```bash
python3 scripts/crew.py delegate /path/TASK.json --backend cursor
```

Use it to spend Cursor plan quota on a slice. Never from Cursor itself.

## Before the first run

Tell the user two things:

- **No OS sandbox.** Cursor's sandbox does not start on this machine (an
  AppArmor error), so the run uses `--sandbox disabled`. crew's hooks are the
  only limit, as with opencode. Do not use Cursor for a slice where an escape
  is expensive.
- **Workspace trust.** The run passes `--trust`, which marks the repo as
  trusted in Cursor for good (`~/.cursor/projects/<repo>/.workspace-trusted`).

## The run

`cursor-agent -p --output-format stream-json --force --trust --sandbox
disabled --model <model>`, at the repo root.

- **Hooks.** `.cursor/hooks.json` is written into the repo for the run and
  removed after, like agy's `.agents/hooks.json`. If one already exists, crew
  refuses. Its `preToolUse` is `failClosed`, so a crashed guard denies.
- **Gate.** `stop` hooks do not fire in `-p`, so the gate is an outer loop, as
  with opencode. After each run crew runs the gate; while it fails, it resumes
  the chat (`--resume <chat>`) with the gate's output, up to
  `max_gate_attempts`.

## Guard

`Read`, `List`, `Grep`, `Write` (edits too), `Delete` and `Shell` are
translated to agy's names and go through the same path, scope, secret and
command rules. Writes into `.cursor/` are denied. Any other tool (Fetch, MCP,
ComputerUse, shell stdin) is denied by the allowlist.

## Task fields

| Field | Meaning |
|---|---|
| `model` | default `auto`; a flat id from `cursor-agent models` (`grok-4.7-xhigh`), or a full bracket variant with every parameter in the CLI's order (`grok-4.7[context=500k,reasoning_effort=xhigh,fast=false]` for Grok's 500k window) |
| `effort` | appended to a flat id (`grok-4.7` + `xhigh` = `grok-4.7-xhigh`); ignored with `auto`; refused with a bracket variant, which carries its own |
| `scope` | must not cover `.cursor/hooks.json` |

## Failures only cursor has

| Failure | Why it exists |
|---|---|
| refused: `.cursor/hooks.json` exists | the run's guard would overwrite it |
| no `result` event, or not `success` | the run was cut or failed; exit 0 says nothing |
| hooks did not load (no sessionStart) | the run had no limit at all |

Cursor leaves a `worker-server` and language servers running after a run.
They carry `CREW_RUN`, so crew stops them and lists them under `warnings`.

## Review

`crew.py ask cursor` and `crew.py review --backend cursor` run in `--mode ask`,
with no crew hooks. They also pass `--trust`, so the folder stays trusted in
Cursor. A two-turn ask passed on 2026.10.22.
