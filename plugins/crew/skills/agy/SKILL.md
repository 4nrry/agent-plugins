---
name: agy
description: Specifics of crew's default backend, agy (Antigravity CLI, Gemini) — run flags, default model gemini-3.8-flash-high, escalation to gemini-4-argon-medium then claude-sonnet-5-5-medium, never Opus, the quota preflight, workspace hooks in .agents/hooks.json, and the background commands agy waits on. Use when delegating a slice or asking for a review through agy.
---

# crew through agy

Read the `delegate` skill first. Commands below run from the `delegate`
skill's directory.

## The run

```bash
python3 scripts/crew.py delegate /path/TASK.json [--model slug] [--no-quota-probe]
```

It runs `agy -p <prompt> --model <m> --output-format json --json-schema
<report> --print-timeout <s> --dangerously-skip-permissions` at the repo root.
Skip-permissions is required (headless `run_command` is auto-denied
otherwise); the hooks are the limit. Tell the user that in the first question.
`--sandbox` confined no writes in tests: do not rely on it.

## Model and escalation

- Start on `gemini-3.8-flash-high`.
- If Flash cannot do a slice (red gate to the limit, or a diff that fails
  review), move to `gemini-4-argon-medium` (its own weekly quota on Pro);
  `-high` only if `-medium` fails too.
- Then `claude-sonnet-5-5-medium`. **Never Opus**: agy's Claude models share
  one weekly quota and Opus drains it in a few slices.
- The model is validated against `agy models`.

## Quota

The preflight reads `agy -p /usage` (no model turn) and refuses, exit 2, when
the model's group has under `min_quota` (default 0.05) left, with the reset
time. The group is found by model line (`flash`, `argon`, `sonnet`, `oss`),
then by family. `--no-quota-probe` skips it. With agy's quota gone, opencode is
the free alternative.

## Before the first run

- **No `.agents/hooks.json` in the repo.** The script writes its own for the
  run, removes it afterwards (also on SIGTERM/SIGHUP), and refuses if one
  exists. After a SIGKILL the next run refuses and names the file to remove.
- **The hooks must load**: without a registered `SessionStart` the verdict
  fails. Do not edit `~/.gemini` to fix it; tell the user.
- A version other than the tested one is a warning in the verdict.

## Guard and gate

- `PreToolUse` with a tool allowlist: file tools and `run_command` only;
  network, subagents, workflows and MCP are denied. agy's renamed file tools
  (`read_file`, `edit_file`, `write_file`) are checked like the old ones.
- The gate runs on the `finish` tool (the `--json-schema` one) and on `Stop`,
  denying "done" while it fails, up to `max_gate_attempts`.

## Background commands

agy moves long `run_command`s to a background task after a few seconds and
then waits up to its print timeout for them after the worker stops. Once the
worker ends with a green gate, the script waits 15 s and stops the commands the
worker left (only processes carrying the run's mark, never agy or MCP
servers); they are listed in `agy.background_killed`. That is expected.

## Failures only agy has

| Failure | Why it exists |
|---|---|
| print timeout | agy exits 0 with partial output |
| `structured_output` null | agy returns `SUCCESS` and exit 0 without a report |
| `denied_actions` / auto-denied | a refused action exits 0 |
| hooks did not load | see above |

## Review

```bash
python3 scripts/crew.py review --diff HEAD~1 --prompt-file /path/question.md
```

Runs in `--mode plan` without skip-permissions, with an empty scope and the
same path guards, and checks that the tree did not change.
