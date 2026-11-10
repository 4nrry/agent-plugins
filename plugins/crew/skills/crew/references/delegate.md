# Delegating a slice to a worker

## Contents

- One run, start to finish
- Ask first
- When to delegate
- Before the first run in a project
- The task
- Run
- The verdict
- Review the diff

You plan, write the task, set scope and gate, read the verdict and review the
diff. The worker executes one slice, headless. It never decides design,
commits, or declares anything done. `scripts/crew.py` is the guard rail.
`delegate` drives seven backends, each with its own guard: [agy.md](agy.md),
[opencode.md](opencode.md), [copilot.md](copilot.md), [codex.md](codex.md),
[grok.md](grok.md), [cursor.md](cursor.md), [claude.md](claude.md).

## One run, start to finish

1. Ask the user, if this backend has not run yet in the session.
2. Commit, so the tree is clean.
3. Write the task JSON outside the tree.
4. `gate TASK.json --baseline` exits 0.
5. `delegate TASK.json` in the background; leave the tree alone.
6. Read the verdict: `ok`, `failures`, `warnings`, `guard_denials`.
7. Review `git diff HEAD` against the source of truth.
8. Commit or discard. The worker never commits.

Each step is detailed below.

## Ask first

Delegating and reviewing send the prompt, the files the worker reads and the
diff to the backend's provider (Google, the Zen model's provider, GitHub) and
spend the user's quota or credits. Ask before the first run on each backend
in a session.

## When to delegate

- A concrete source of truth exists: legacy code to port, a spec, a schema, an
  approved example of the same pattern.
- A mechanical gate runs in minutes: tests, typecheck, lint, formatter.
- The scope fits in a few globs. Best of all, it repeats: review the first
  slice line by line, then the pattern is set.

Do not delegate exploration, unknown bugs, architecture or public-API
decisions, naming, changes spread across many directories, anything needing
install, network, migrations or deploys, or a change cheaper to make than to
review.

## Before the first run in a project

1. Clean tree: the script refuses a dirty one. Commit first.
2. Green baseline: `python3 scripts/crew.py gate TASK.json --baseline`. A red
   gate before the start makes the worker hunt for the gate instead of fixing
   code.

## The task

A JSON **outside the tree** (scratchpad, or `$(git rev-parse --git-path crew)/tasks/`).
Example: [task.example.json](task.example.json).

| Field | Meaning |
|---|---|
| `prompt` / `prompt_file` | the brief (file path relative to the JSON) |
| `scope` | globs from the repo root (`*` crosses `/`); the only files the worker may write |
| `gate.forbid` | regexes against **added** lines (`any`, `@ts-ignore`, `.skip(`) |
| `gate.format` | the formatter; `{files}` becomes the changed in-scope files |
| `gate.checks` | lint, typecheck, narrow tests; all must exit 0 |
| `side_effects` | globs tools rewrite on their own (`nx.json`); tolerated, listed |
| `backend`, `model`, `effort` | `agy` (default), `opencode`, `copilot`, `codex`, `grok`, `cursor`, `claude`; models in each backend's file; `effort` for codex, grok, cursor and claude |
| `timeout`, `gate_timeout`, `max_gate_attempts` | defaults `30m`, 900 s per command, 5 |
| `allow_paths`, `deny_commands`, `secret_globs` | extra readable paths, extra denied command regexes, secret file names (default: `.env`, `.env.*`, `.dev.vars`, `.dev.vars.*`, `*.pem`, `*.key`, `*.p12`, `*.pfx`, `id_rsa*`, `id_ed25519*`, `id_ecdsa*`, `id_dsa*`, except names ending in `.example`, `.sample` or `.template`; `.envrc` is not covered; `[]` disables) |

The brief:

- Name the source of truth and say to read it fully before writing; point to an
  approved example of the same pattern.
- List the required changes and say "only these" — no refactors, renames or
  improvements. Give exact file names.
- Point to paths instead of pasting files (the prompt is a CLI argument; over
  100 KB is refused).
- Do not repeat scope, gate or prohibitions: the script appends them.

The gate: put the formatter in `format` (without it the worker skips
formatting), keep commands fast and deterministic (flaky tests burn
attempts). Gate commands see `CREW_GATE=1`.

Secrets: the name block stops `.env`-style files, not a path built at runtime,
and the worker inherits your environment. Do not delegate with secrets in
environment variables.

## Run

```bash
python3 scripts/crew.py delegate '/path/TASK.json' [--repo repo] [--backend agy|opencode|copilot|codex|grok|cursor|claude] [--model slug]
```

Build the line from the arguments; never paste them raw into the shell.
Runs can exceed 10 minutes: run in the background. **Do not edit that tree
while it runs** — every change is attributed to the worker. One slice per
worktree at a time.

Each run gets a dir under `$(git rev-parse --git-path crew)/runs/`. In a linked
worktree or a submodule, where that path is outside the work tree, it is under
`/tmp/crew-state-<uid>/<hash>/crew/runs/` instead (mode 0700): crew's hooks log
there, and Grok runs them in a sandbox that cannot write the main checkout's
`.git`. The verdict's `run_dir` names it.

## The verdict

Exit 0 = ok, 1 = the run failed, 2 = refused, 130 = interrupted (hooks
removed). A refusal normally comes before the run, with nothing spent; a git
command that fails after the run is reported the same way, so read `failures`
before assuming no quota was used.
The CLI's own exit 0 never counts. `ok: false` always comes with `failures`;
read `warnings` and `guard_denials` too (repeated denials usually mean an
ambiguous brief or an impossible gate). On failure the diff stays in the tree:
finish it by hand or rewrite the task — re-delegating the same task tends to
repeat the error.

The shape, with made-up values for [task.example.json](task.example.json) and
the long strings cut:

```json
{
  "ok": true,
  "mode": "delegate",
  "backend": "agy",
  "run_dir": "/repo/.git/crew/runs/20261110-141502-delegate-48211",
  "model": "gemini-3.8-flash-high",
  "failures": [],
  "warnings": ["1 call(s) denied by the guards; see guard_denials"],
  "changed": {
    "in_scope": ["src/server/orders/orders.service.ts",
                 "src/server/orders/orders.service.test.ts"],
    "side_effects": [],
    "out_of_scope": []
  },
  "gate": {"passed": true, "source": "final (run after agy)",
           "hook_attempts": 2, "tail": "Test Files  1 passed (1)"},
  "guard_denials": [{"tool": "run_command",
                     "reason": "Command blocked (…): 'git commit -am wip'. …",
                     "args": {"CommandLine": "git commit -am wip"}}],
  "stop_events": [],
  "report": {
    "status": "done",
    "files_changed": ["src/server/orders/orders.service.ts",
                      "src/server/orders/orders.service.test.ts"],
    "checks_run": ["npx vitest run src/server/orders PASS"],
    "divergences": ["findById returns null instead of throwing: the new repository has no NotFound"],
    "out_of_scope_needs": ["src/server/index.ts: register the service"],
    "notes": ""
  },
  "agy": {"rc": 0, "wall_seconds": 412},
  "next": "Nothing was committed. Review `git diff HEAD` …"
}
```

`ok` is true here and the run still needs a decision: one divergence to accept
or reject, and one file the worker could not touch. `changed` comes from git
and `gate` from the script; `report` is the worker's own account. The block
named after the backend (`agy` here) carries more fields, which differ by
backend. A refusal prints only `{"ok": false, "refused": true, "failures": […]}`.

## Review the diff — after every run, ok or not

1. Read `git diff HEAD` side by side with the source of truth.
2. Check every `divergences` and `out_of_scope_needs` item; an empty list
   proves nothing.
3. Look for what cheap models do and gates miss: invented aliases or shims,
   "fixes" outside scope, unreported behavior changes, imports inside
   functions, stray blank lines.
4. Ported tests: are all original cases there, with asserts as strong?
5. `report.checks_run` is self-declared; only the gate counts.
6. Commits are yours or the user's, never the worker's.

The guards are a speed bump for a cooperative model that gets lost, not a
sandbox: a command that builds a path at runtime (`python3 -c`) passes them,
and nothing checks ignored directories or paths outside the repo after the run.
