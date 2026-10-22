# crew

Another vendor's agent CLI as an isolated subagent, from whatever tool you work
in. The host agent writes the question or the task and checks the result; the
worker answers, reviews, or runs one slice under guard rails that exist only for
the run. Use it to spend spare quota on another vendor, never for the host's
own models: its native subagents serve those.

```
/plugin install crew@4nrry
```

Other tools get the skill through `just link-skills global` at the repo root.

| Command | Backends | What it does |
|---|---|---|
| `ask` | agy, opencode, Codex, Grok, Hermes, Claude Code; Copilot, Cursor, Muse, Kimi built from `--help`, untested | one read-only turn, or the next turn of a session (`--session`) |
| `review` | every `ask` backend; agy, opencode and Copilot under crew's guard hooks | schema'd findings on a diff or files |
| `delegate` | agy, opencode, Copilot, Codex, Grok | one coding slice under the worker CLI's own hooks and a gate |
| `backends` | all | binary, tiers, effort values, read-only mechanism, last version tested |

Tiers `cheap`, `mid` and `top` map to a model and an effort per backend in
`scripts/backends.py`. Requires `git`, `python3` (stdlib only), Linux (`/proc`)
and the backend's CLI logged in. A run sends the prompt and what the worker
reads to that vendor; the skill makes the host ask first.

| Component | Path |
|---|---|
| Skill | `SKILL.md`: picking a backend and tier, `ask`, `review`, `delegate` |
| Scripts | `scripts/crew.py`, and `scripts/backends.py` with each CLI's argv, parser and tiers |
| References | `references/delegate.md`; per backend `agy.md`, `opencode.md`, `copilot.md`, `codex.md`, `grok.md`; `clis.md` for every agent CLI's flags and folders |
| Hook | `hooks/inject.sh`: `UserPromptSubmit`, one line pointing at the skill when the prompt names a backend |

Every worker carries `CREW_RUN`, and crew refuses to start a worker inside one.
`ask` also fails when the work tree changes, and stops what the run left behind.

## What a delegate does

1. Refuses before spending (exit 2): dirty tree, leftover hooks file, invalid
   task, unknown or disallowed model, too little quota.
2. Installs the worker CLI's own hooks for the run (agy `.agents/hooks.json`,
   an opencode plugin under the run's `OPENCODE_CONFIG_DIR`, copilot
   `.github/hooks/crew-<run>.json`). They allow file tools and the shell only
   inside the repo and scope — paths resolved through symlinks, `.git`,
   redirects, installs, network, background `&` and git writes denied — and
   run the gate before the worker may say "done".
3. Runs the worker, removes the hooks, and judges the run from the CLI's
   events, the gate on the final tree, `git status` against the scope, HEAD and
   git config. The CLI's exit 0 never counts as success.
4. Stops processes the run left behind (they carry `CREW_RUN`), and prints a
   JSON verdict: `ok`, `failures`, `warnings`, files by scope, gate, guard
   denials, the worker's report and usage.

Run state lives in `$(git rev-parse --git-path crew)/runs/`, outside the tree.
Nothing is committed; on failure nothing is reverted.

A hook points at the skill because, in this repo's agent-fleet eval, a skill
description fired on 2 of 30 should-trigger runs. This hook's own hit rate is
not measured.

The guards are a speed bump for a cooperative model, not a sandbox: a path
built at runtime (`python3 -c`) passes them.

## Evidence and checks

`just check` runs `crew.py --self-test` (no CLI is called). Lab and smoke
notes: [`bench/plugins/crew/results/`](../../bench/plugins/crew/results/).
No comparison with the host doing the same work exists, so no saving is claimed.

Upgrading from 0.5.x: the skills `delegate`, `review`, `agy`, `opencode` and
`copilot` became one skill, `crew`, with the backend notes under `references/`;
`crew.py` moved to `scripts/` at the plugin root.

Upgrading from `agy-worker` (≤ 0.3.x): run state moved from
`$(git rev-parse --git-path agy-worker)` to `--git-path crew`, and
`AGY_WORKER_RUN` became `CREW_RUN`.
