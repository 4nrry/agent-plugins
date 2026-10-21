---
name: delegate
description: Delegates one well-bounded slice of coding work to a cheap headless worker — agy (Gemini), opencode (a free Zen model) or GitHub Copilot CLI (no shell) — under guard hooks and a mechanical gate, and returns a JSON verdict. Covers when to delegate and when not, how to write the task and the gate, reading the verdict, and the mandatory diff review. Use when a task has a concrete source of truth and a fast gate (port a module, add tests to a spec, repeat a pattern across files), or when the user asks to delegate, offload or farm out work to agy, opencode or Copilot.
argument-hint: <task.json> [--backend agy|opencode|copilot] [--model slug] [--no-quota-probe]
---

# Delegating a slice to a worker

You plan, write the task, set scope and gate, read the verdict and review the
diff. The worker executes one slice, headless. It never decides design,
commits, or declares anything done. `scripts/crew.py` (in this skill's
directory) is the guard rail; backend specifics are in the `agy`, `opencode`
and `copilot` skills.

## Ask first

Delegating and reviewing send the prompt, the files the worker reads and the
diff to the backend's provider (Google, the Zen model's provider, GitHub) and
spend the user's quota or credits. Ask before the first `delegate` or `review`
of a session.

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
Example: [references/task.example.json](references/task.example.json).

| Field | Meaning |
|---|---|
| `prompt` / `prompt_file` | the brief (file path relative to the JSON) |
| `scope` | globs from the repo root (`*` crosses `/`); the only files the worker may write |
| `gate.forbid` | regexes against **added** lines (`any`, `@ts-ignore`, `.skip(`) |
| `gate.format` | the formatter; `{files}` becomes the changed in-scope files |
| `gate.checks` | lint, typecheck, narrow tests; all must exit 0 |
| `side_effects` | globs tools rewrite on their own (`nx.json`); tolerated, listed |
| `backend`, `model` | `agy` (default), `opencode`, `copilot`; models in each backend skill |
| `timeout`, `gate_timeout`, `max_gate_attempts` | defaults `30m`, 900 s per command, 5 |
| `allow_paths`, `deny_commands`, `secret_globs` | extra readable paths, extra denied command regexes, secret file names (default covers `.env*`, `.dev.vars`, `*.pem`, `*.key`, `id_rsa*`; `[]` disables) |

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
python3 scripts/crew.py delegate '/path/TASK.json' [--backend agy|opencode|copilot] [--model slug]
```

Build the line from the arguments; never paste them raw into the shell.
Runs can exceed 10 minutes: run in the background. **Do not edit that tree
while it runs** — every change is attributed to the worker. One slice per
worktree at a time.

## The verdict

Exit 0 = ok, 1 = the run failed, 2 = refused before running (nothing spent).
The CLI's own exit 0 never counts. `ok: false` always comes with `failures`;
read `warnings` and `guard_denials` too (repeated denials usually mean an
ambiguous brief or an impossible gate). On failure the diff stays in the tree:
finish it by hand or rewrite the task — re-delegating the same task tends to
repeat the error.

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
