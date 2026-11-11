# crew through agy

Read [delegate.md](delegate.md) first. `scripts/crew.py` is in the crew skill's
directory; run it from the task's repository, or pass `--repo`.

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

## Ask on agy 1.5

`ask` used to rely on `--mode plan` to keep agy from writing. On agy 1.5.5
that did not hold in print mode: asked to create a file, it did, with and
without `--disable-slash-commands` (with it, agy also prints that plan mode
has no effect). Shell commands were still denied.

Where `agy --help` lists `--settings` (settings for one session, never
saved), crew passes `{"permissions":{"deny":["write_file(*)","command(*)","mcp(*)"]}}`.
With it agy 1.5.5 answered "Permission denied for write_file(...). Matches
user-configured deny rule" and wrote nothing, in the `--web` directory and in
a repository; web search still ran. The verdict's `read_only` names the
rules.

An agy at 1.5 or later without that flag, or one whose version cannot be
read, is not read-only: the verdict says so in `read_only` and in a warning.
Use `--web` there, where a write in the working directory goes with it; from
a repository the work-tree check fails the run for a new or changed tracked
file only. `review` and `delegate` run under crew's hooks and are not
affected by any of this.

## Review

```bash
python3 scripts/crew.py review --diff HEAD~1 --prompt-file /path/question.md
```

Runs in `--mode plan` without skip-permissions, with an empty scope and the
same path guards, and checks that the tree did not change.
