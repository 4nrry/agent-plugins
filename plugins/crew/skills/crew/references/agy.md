# crew through agy

Read [delegate.md](delegate.md) first. `scripts/crew.py` is in the crew skill's
directory; run it from the task's repository, or pass `--repo`.

## Contents

- The run
- Model and escalation
- Quota
- Before the first run
- Guard and gate
- Background commands
- Failures only agy has
- Ask on agy 1.5
- Review
- Seen on agy 1.5.6

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
- **The hooks must load**: without a registered `SessionStart` a delegate
  verdict fails (for `review`, see the table below). Do not edit `~/.gemini`
  to fix it; tell the user.
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

agy 1.5.6 ends its own background tasks when it exits ("terminating 1 daemon
task(s) on exit"), with no wait, so there the list stays empty.

## Failures only agy has

| Failure | Why it exists |
|---|---|
| print timeout | agy 1.4 exits 0 with partial output; 1.5.6 exits 3 with status `ERROR` |
| `structured_output` null | agy returns `SUCCESS` and exit 0 without a report |
| `denied_actions` / auto-denied | a refused action exits 0 |
| hooks did not load | see above |

## Ask on agy 1.5

`ask` used to rely on `--mode plan` to keep agy from writing. On agy 1.5.5
that did not hold in print mode: asked to create a file, it did, with and
without `--disable-slash-commands` (with it, agy also prints that plan mode
has no effect). Shell commands were still denied.

Where `agy --help` lists a `--settings` flag (settings for one session, never
saved), crew passes `{"permissions":{"deny":["write_file(*)","command(*)","mcp(*)"]}}`.
With it agy 1.5.5 answered "Permission denied for write_file(...). Matches
user-configured deny rule" and wrote nothing: creating a file, on a first and
on a resumed turn, and editing, deleting and renaming existing ones. Web
search and `--schema` still worked. The verdict's `read_only` says the rules
were passed, and a warning lists any tool call agy refused.

What the rules leave open: agy can still read any file it is given a path to
and can still fetch a URL (`read_file` and `execute_url` are not denied), and
its MCP servers are refused, so an answer that needed one comes back poorer.
Whether the session's rules add to the user's own or replace them was not
checked.

An agy whose help does not list the flag, or cannot be read, gets no rules.
At 1.5 or later, or with a version that cannot be read, such an agy is not
read-only: the verdict says so in `read_only` and in a warning. Use `--web`
there, where a write in the working directory goes with it; from a
repository the work-tree check fails the run for a new or changed tracked
file only.

`delegate` does not use these rules: it has to write, and crew's hooks are
its guard. On agy 1.5.6 they held: a write outside the scope and a shell
command reaching into `.agents` were denied, the gate ran on `finish` and on
`Stop`, and the verdict was green.

## Review

```bash
python3 scripts/crew.py review --diff HEAD~1 --prompt-file /path/question.md
```

Runs in `--mode plan` without skip-permissions, with an empty scope and the
same path guards, and checks that the tree did not change. Where agy takes
`--settings`, the deny rules of the section above are passed too
(`agy.deny_settings` in the verdict).

The hooks are the guard. They loaded on agy 1.5.5 and 1.5.6, and on 1.5.6
denied every write a reviewer was asked to make and a read outside the
repository. The deny rules are what is left if the hooks do not load: with
review's flags and no hooks file, agy 1.5.6 created one file and changed two
under plan mode alone, and wrote nothing once the rules were passed.

| Hooks loaded | agy takes `--settings` | Verdict |
|---|---|---|
| yes | either | as usual |
| no | yes | warning: plan mode and the deny rules, no path guard on reads |
| no | no, agy 1.5 or later, or a version that cannot be read | failure: nothing kept the review read-only |
| no | no, before 1.5 | warning: plan mode only |

## Seen on agy 1.5.6

One delegate run each, Flash, 2026-11-11; the record is the
agy-delegate-1.5.6 claims file under
[bench/plugins/crew/results](https://github.com/4nrry/agent-plugins/tree/main/bench/plugins/crew/results).

| Case | What happened |
|---|---|
| `finish` before any work | denied with the gate's output; the worker did the work and the second `finish` passed |
| a command left running | agy ended it on exit; the verdict was green and `agy.background_killed` empty |
| print timeout | exit 3, status `ERROR`, the running command ended by agy; the verdict failed |
| no report | agy asked the model for it four times by itself, then `Stop` with `MAX_FORCED_INVOCATIONS`, status `SUCCESS`, report null; the verdict failed |

Not seen on 1.5.6: a `Stop` with `NO_TOOL_CALL`, crew's own request for the
missing report, a `Stop` answered `continue` after a red gate, and the
watcher stopping a command (agy got there first). The gate that runs after
agy decides the verdict in every one of them.
