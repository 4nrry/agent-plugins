# crew through opencode

Read [delegate.md](delegate.md) first. Commands run from the crew skill's
directory (the one holding `SKILL.md`). Requires opencode 2.x on PATH or in `~/.opencode/bin`; 1.x
is refused.

```bash
python3 scripts/crew.py delegate /path/TASK.json --backend opencode [--model opencode/<model>]
```

Use it when agy's quota is gone, or for extra slices at no cost.

## Models and data

Only these six are accepted. Zen rotates its free models: on 2026-10-22
minimax left (`provider.no-route`), so the default and the `cheap` tier are
deepseek, `mid` is glm, and `top` is Nemotron Super VL (1M context, but NVIDIA
logs the prompts). Terms from the Zen docs; re-read them before relying on this
table, they change:

| Model | Data terms |
|---|---|
| `opencode/minimax-m3.1-flash-free` (unavailable since 2026-10-22) | zero retention, no training |
| `opencode/deepseek-v4.1-flash-free` (default) | zero retention, no training |
| `opencode/glm-5.3-flash-free` | zero retention, no training |
| `opencode/nemotron-3.5-super-vl-free` | logged by NVIDIA to improve its products: no personal or confidential data |
| `opencode/nemotron-3.5-lightning-free` | same as Super VL |
| `opencode/mimo-v2.6-flash-free` | prompts may be used to improve the model while free |

## The guard is weaker — tell the user

Path, scope and command rules are agy's (a generated plugin forwards every
tool call to `crew.py hook oc-pre`), but there is no process-level tool
allowlist or plan mode, everything depends on the plugin loading (without its
start event the run fails), and the backend also denies `cp`, `mv`, `touch`,
`mkdir`, `rm`, `truncate` and `patch` in the shell. `execute` (a JS sandbox
with `fetch()`) is denied. Do not use opencode for a slice where an escape is
expensive.

## How the run works

- Each run is `opencode run --standalone` in the repo, so it does not attach
  to a shared background service (the desktop app's) that would not see the
  run's environment.
- The guard is a 2.x plugin in `<run dir>/oc-config/plugins/`, loaded through
  `OPENCODE_CONFIG_DIR`; nothing goes into the tree or `~/.config`. The run's
  config (`external_directory: deny`) goes through `OPENCODE_CONFIG_CONTENT`.
- The worker loads your `~/.claude/CLAUDE.md`, like a native subagent;
  `"disable_claude_code": true` in the task turns that off.
- opencode writes `"$schema"` into the cwd's `opencode.json`; the script saves
  and restores `opencode.json`/`.jsonc` around every process. Do not cover
  `opencode.json` in `scope`.
- Runs sometimes hang at server start; the task timeout ends them.

## Gate and report

- The gate is an outer loop: each attempt is `opencode run -s <session>` with
  the gate's output. `max_gate_attempts` counts runs.
- The report is text: the last JSON object in the final message; the loop asks
  again if it is missing.
- Success comes from the events (no `error`, the run ends on its final text
  event) plus the gate; exit 0 does not count.

## Failures only opencode has

| Failure | Why it exists |
|---|---|
| guard plugin did not load | no start event: the run had no guard rails |
| `error` event, or the run ended mid-step | opencode exits 0 on API errors and cut runs |
| report missing | no JSON object in the final message, even after asking again |

## Review

```bash
python3 scripts/crew.py review --backend opencode --diff HEAD~1 --prompt-file /path/question.md
```

No plan mode: empty scope, and the plugin denies every shell command.

## Web search (`ask --web`)

opencode 2.1 searches only through a provider picked once in its TUI. With
none saved it asks, and a headless run cancels the question ("Web search
cancelled", exit 1). crew's web profile loads a plugin, from the run dir, that
picks Exa for that run only; the user's saved choice is not touched. The
queries go to Exa (`mcp.exa.ai`, no key).
