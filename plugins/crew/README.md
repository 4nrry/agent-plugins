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
| `ask` | agy, opencode, Codex, Grok, Hermes, Claude Code, Copilot, Cursor; Muse, Kimi built from `--help`, untested | one read-only turn, or the next turn of a session (`--session`); `--web` for web search, `--schema` for a JSON object back |
| `review` | every `ask` backend; agy, opencode and Copilot under crew's guard hooks | schema'd findings on a diff or files |
| `delegate` | agy, opencode, Copilot, Codex, Grok, Cursor, Claude Code (from another host) | one coding slice under the worker CLI's own hooks and a gate |
| `backends` | all | binary, tiers, effort values, read-only mechanism, last version tested |

Tiers `cheap`, `mid` and `top` map to a model and an effort per backend in
`scripts/backends.py`. Requires `git`, `python3` (stdlib only), Linux (`/proc`)
and the backend's CLI logged in; the hook also needs `jq` and does nothing
without it. A run sends the prompt and what the worker reads to that vendor;
the skill makes the host ask first.

It runs where local agent CLIs do: Claude Code and the other terminal agents
on Linux. claude.ai chat and Cowork cannot run it, and the hook is Claude Code
only.

The skill lives in `skills/crew/` (paths below are relative to it, except
`hooks/` at the plugin root), and an Agent Plugins `plugin.json` at the root
lets Copilot, Codex and Cursor install the plugin.

| Component | Path |
|---|---|
| Skill | `SKILL.md`: picking a backend and tier, `ask`, `review`, `delegate` |
| Scripts | `scripts/crew.py`, `scripts/backends.py` with each CLI's argv, parser and tiers, and `scripts/crew_selftest.py` with crew.py's self-test |
| References | `references/delegate.md`; per backend `agy.md`, `opencode.md`, `copilot.md`, `codex.md`, `grok.md`, `cursor.md`, `claude.md`; `clis.md` for every agent CLI's flags and folders |
| Hook | `hooks/inject.sh`: `UserPromptSubmit`, one line pointing at the skill when the prompt names agy, opencode, copilot, codex, grok, hermes, kimi or muse as a whole word (not claude or cursor, which more often name the host or an editor) |

Every worker carries `CREW_RUN`, and crew refuses to start a worker inside one.
`ask` also fails when the work tree changes, and stops what the run left behind.

## What a delegate does

1. Refuses before spending (exit 2): dirty tree, leftover hooks file, invalid
   task, too little quota, and for agy, opencode and Copilot an unknown or
   disallowed model.
2. Installs the worker CLI's own hooks for the run: agy `.agents/hooks.json`,
   an opencode plugin under the run's `OPENCODE_CONFIG_DIR`, copilot
   `.github/hooks/crew-<run>.json`, codex as `-c hooks.*` arguments, grok
   `~/.grok/hooks/crew-<run>.json` in the user's home, cursor
   `.cursor/hooks.json`, claude a settings file in the run directory. They
   allow file tools and the shell only inside the repo and scope — paths
   resolved through symlinks, `.git`, redirects, installs, network and
   background `&` denied, and of git only the read commands plus `add`, `rm`
   and `mv` (no commit, push, checkout, reset or stash) — and run the gate
   before the worker may say "done".
3. Runs the worker, removes the hooks, and judges the run from the CLI's
   events, the gate on the final tree, `git status` against the scope, HEAD and
   git config. The CLI's exit 0 never counts as success.
4. Stops processes the run left behind (they carry `CREW_RUN`), and prints a
   JSON verdict: `ok`, `failures`, `warnings`, files by scope, gate, guard
   denials, the worker's report and usage.

Run state lives in `$(git rev-parse --git-path crew)/runs/`, outside the tree.
In a linked worktree or a submodule, where that path is outside the work tree,
it lives in `/tmp/crew-state-<uid>/<hash>/crew/runs/` (mode 0700), since Grok
runs crew's hooks in a sandbox that cannot write the main checkout's `.git`.
Nothing is committed; on failure nothing is reverted.

A hook points at the skill because, in this repo's agent-fleet eval, a skill
description fired on 2 of 30 should-trigger runs. This hook's own hit rate is
not measured.

The guards are a speed bump for a cooperative model, not a sandbox: a path
built at runtime (`python3 -c`) passes them.

## Evidence and checks

`just check` runs `crew.py --self-test` (no CLI is called). Lab and smoke
notes: [`bench/plugins/crew/results/`](https://github.com/4nrry/agent-plugins/tree/main/bench/plugins/crew/results).
No comparison with the host doing the same work exists, so no saving is claimed.

Upgrading from 0.5.x: the skills `delegate`, `review`, `agy`, `opencode` and
`copilot` became one skill, `crew`, with the backend notes under `references/`;
`crew.py` moved to `scripts/`. From 0.13.0 the skill folder is `skills/crew/`
(Agent Plugins layout); set `CREW_PY` again if you pinned the old path (it is
agent-fleet's `fleet_worker.py` that reads it, not crew).

Upgrading to 0.15.2: in a linked worktree, new runs go to
`/tmp/crew-state-<uid>/`; earlier ones stay in the main checkout's
`.git/worktrees/<name>/crew/`.

Upgrading to 0.15.3: a Grok delegate no longer needs the repo trusted in Grok.
A trust given only for crew can be withdrawn with `/hooks-untrust` in a Grok
session there; the worker then stops reading the repo's `AGENTS.md` and
`CLAUDE.md`, and the verdict says so.

Upgrading from `agy-worker` (≤ 0.3.x): run state moved from
`$(git rev-parse --git-path agy-worker)` to `--git-path crew`, and
`AGY_WORKER_RUN` became `CREW_RUN`.
