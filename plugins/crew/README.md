# crew

Cheap headless workers through other agent CLIs, without fighting Claude's
harness: Claude plans, writes the task, sets scope and gate and reviews the
diff; the worker runs one slice under guard rails that exist only for the run.

```
/plugin install crew@4nrry
```

| Backend | CLI | When |
|---|---|---|
| `agy` (default) | Antigravity CLI, Gemini | primary |
| `opencode` | opencode 2.x, free Zen models | agy's quota is gone, or extra capacity; weaker shell guard |
| `copilot` | GitHub Copilot CLI, Free plan | another model family; no shell, paid in AI credits |

Requires `git`, `python3` (stdlib only), Linux (`/proc`) and the backend's CLI
logged in. Delegating sends the prompt, the files the worker reads and the diff
to the backend's provider; the skills make Claude ask before the first run.

| Component | Path |
|---|---|
| `/crew:delegate` | `skills/delegate/` — when to delegate, the task, the verdict, the diff review; `scripts/crew.py` and `references/task.example.json` |
| `/crew:review` | `skills/review/` — read-only second opinion |
| Backend skills | `skills/agy/`, `skills/opencode/`, `skills/copilot/` — flags, models, what each guard does and does not |
| Hook | `hooks/inject.sh` — `UserPromptSubmit`: injects the backend skill when the prompt names `agy`, `opencode` or `copilot` as a whole word |

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

A hook triggers the skills because, in this repo's agent-fleet eval, a skill
description fired on 2 of 30 should-trigger runs. This hook's own hit rate is
not measured.

The guards are a speed bump for a cooperative model, not a sandbox: a path
built at runtime (`python3 -c`) passes them.

## Evidence and checks

`just check` runs `crew.py --self-test` (no CLI is called). Lab and smoke
notes, including today's agy 1.4.4 and opencode 2.1.2 runs:
[`bench/plugins/crew/results/`](../../bench/plugins/crew/results/). No
comparison with Claude doing the same slice exists, so no saving is claimed.

Upgrading from `agy-worker` (≤ 0.3.x): run state moved from
`$(git rev-parse --git-path agy-worker)` to `--git-path crew`, and
`AGY_WORKER_RUN` became `CREW_RUN`.
