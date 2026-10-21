---
name: copilot
description: Specifics of crew's GitHub Copilot CLI backend — Free plan with --model auto only, every run paid in AI credits, a worker with no shell whose whole gate runs at agentStop, COPILOT_ALLOW_ALL set only for the run's process, and a worker that claims checks it could not have run. Use when delegating a slice or asking for a review through Copilot CLI.
---

# crew through Copilot CLI

Read the `delegate` skill first. Commands below run from the `delegate`
skill's directory. Requires `copilot` on PATH and logged in; a version other
than the tested one is a warning.

```bash
python3 scripts/crew.py delegate /path/TASK.json --backend copilot
```

## When to use

Rarely, and knowing it costs: the Free plan has no free quota, so every run
spends AI credits (well under one per small run). It fits a slice where a model
from another family is wanted and **the whole gate runs without the worker**:
it has no shell, so it cannot run tests, formatters or git. The brief must be
enough without running anything.

## Before the first run

Ask the user: the code goes to GitHub and each run spends credits. Also say
that the run sets `COPILOT_ALLOW_ALL=true` for the copilot process only — the
only way the repo's hooks load — which also loads the repo's own skills,
plugins, MCP servers and hooks (the verdict warns about hooks it finds in
`.github/hooks/`). Do not use it in a checkout you do not trust.

## Model and credits

- Only `auto` is accepted. On a paid plan `"copilot_model_override": true`
  allows another slug — an untested path; say so.
- `max_ai_credits`: default and minimum 30 (the CLI refuses less). A brake on a
  runaway run, not a budget.
- **Report `copilot.usage.ai_credits` to the user** after every run.

## No shell

- The run passes `--excluded-tools bash task`. Never exclude `bash` without
  `task`: excluding only `bash` sent the worker into thousands of `task`
  subagent calls.
- A shell or `task` call in the event stream fails the run.
- The whole gate (scope, `forbid`, `format`, `checks`) runs on crew's side at
  `agentStop`, which blocks with the gate's output up to `max_gate_attempts`
  (**at most 8**: the CLI ignores the hook after 8 blocks in a row). Tell the
  worker in the brief what it needs to know about the commands.
- `report.checks_run` is even less reliable here: the worker has reported a
  passing test it could not have run. Only the gate counts.

## Task fields

| Field | Meaning |
|---|---|
| `max_gate_attempts` | at most 8 |
| `max_ai_credits` | default and minimum 30 |
| `copilot_model_override` | `true` to accept a model other than `auto` (untested) |
| `scope` | must not cover `.github/hooks/`, `.github/copilot/settings*.json` or `.claude/settings*.json`: copilot loads hooks from there |

The run writes `.github/hooks/crew-<run>.json` and removes it at the end. After
a SIGKILL the next run refuses and names the file to remove.

## Failures only copilot has

| Failure | Why it exists |
|---|---|
| hooks did not load (no hook event) | without the exact `COPILOT_ALLOW_ALL=true` the hooks vanish silently |
| shell or subagent call observed | `bash` and `task` should have been excluded |
| no `result` event, or `exitCode` not 0 | the run was cut; the process's exit 0 proves nothing |
| the run's hooks file changed | the guard may have been replaced mid-run |

## Review

```bash
python3 scripts/crew.py review --backend copilot --diff HEAD~1 --prompt-file /path/question.md
```

No shell and no `apply_patch` (`--excluded-tools bash task apply_patch`), with
the hook denying every write. Report the credits.
