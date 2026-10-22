# crew through Codex

Read [delegate.md](delegate.md) first. Commands run from the crew skill's
directory (the one holding `SKILL.md`). Requires `codex` on PATH and logged in;
a version other than the tested one is a warning.

```bash
python3 scripts/crew.py delegate /path/TASK.json --backend codex
```

Use it to spend ChatGPT plan quota on a slice, or for a model family other
than the host's. Never from Codex itself.

## The run

`codex exec --json -s workspace-write -c approval_policy="never"` at the repo
root, plus `-m <model>` and, with `"effort"` in the task,
`-c model_reasoning_effort="<effort>"`. Two layers keep it in bounds:

- **The OS sandbox.** `workspace-write` confines writes to the repo and turns
  the network off.
- **crew's hooks.** They go in as `-c hooks.SessionStart|PreToolUse|Stop=...`
  for this run only, so nothing is written into the tree or `~/.codex`.
  `--dangerously-bypass-hook-trust` lets those per-run hooks run without a
  trust entry. Your own hooks in `~/.codex/hooks.json` run too.

## Guard and gate

- `PreToolUse`: the shell (`Bash`) and every file touched by an `apply_patch`
  go through the same path, scope, secret and command rules as agy. Shell
  redirects that write are denied, so the worker edits with `apply_patch`.
  MCP tools are denied.
- `Stop`: the gate runs. While it fails, the stop is blocked and its output
  becomes the next prompt, up to `max_gate_attempts`. Once the gate is green,
  the stop is blocked at most twice more if the final message lacks the JSON
  report.

## Task fields

| Field | Meaning |
|---|---|
| `model` | default `gpt-6-luna`; `codex debug models` lists the others |
| `effort` | `low` to `ultra`, as the model offers |

## Failures only codex has

| Failure | Why it exists |
|---|---|
| no `turn.completed` event | the run was cut; the exit code says nothing |
| `error` or `turn.failed` event | Codex exits 0 on some of these |
| hooks did not load (no SessionStart) | without them the run had only the sandbox |

## Review

`crew.py review --backend codex` runs through `ask`, in the `read-only`
sandbox, with no crew hooks.
