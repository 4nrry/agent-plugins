# Batch 2026-11-09-grok-worktree-state — claims

**Smoke notes, not run records.** Grok Build 1.0.77, grok-4.7 at crew's
default effort (medium), Codex CLI 0.167.0; n=1 per case. One throwaway repo
outside /tmp, with a linked worktree inside it at `.claude/worktrees/wt1`,
where Claude Code desktop puts its sessions' worktrees; trusted in Grok for the
batch and untrusted after it. Logs stayed in the session scratchpad and were
not committed.

The repo sat outside /tmp on purpose: Grok's sandbox writes /tmp, so a main
checkout there would have hidden the bug.

## The bug

crew keeps a run's state in `git rev-parse --git-path crew`. In a linked
worktree that is `<main checkout>/.git/worktrees/<name>/crew`, outside the work
tree, and Grok runs crew's hooks inside `--sandbox workspace`, which writes
only in the work tree, `~/.grok`, `/tmp` and `/var/tmp` (Grok's sandbox
guide). The hooks could not open their log, so every Claude Code desktop
session hit it. First seen in another repository's sessions the same day,
then reproduced here.

| Case | crew | Result |
|---|---|---|
| slugify delegate in the worktree (brief asks for one write outside scope first) | 0.15.1 | `ok: false` in 77 s: no `guard.jsonl` in the run dir, so "the crew hooks did not load (no SessionStart logged)"; the worker reported every call (an MCP call, the out-of-scope write, `read_file`, `grep`, `list_dir`, the shell) denied as `internal guard failure (PermissionError(13, 'Permission denied'))` and declared itself `blocked`; the tree stayed clean |
| `grok -p --sandbox workspace --add-dir <git path>`, an unknown model id | — | refused before any request: `sandbox profile 'workspace' doesn't let the session write there` |
| same delegate | 0.15.2 | `ok` in 59 s: SessionStart logged, the MCP call and the out-of-scope `NOTES.md` write denied, gate green at the first Stop, report `done`, hook file removed; run dir under `/tmp/crew-state-<uid>/`, top dir 0700 |

The 0.15.2 diff matched the brief (`import re` at module level, three tests,
`TitleWordsTest` untouched).

## Codex and the other backends

| Probe (no model turn) | worktree's git dir | `/tmp` |
|---|---|---|
| `codex sandbox -P :workspace` (the `workspace-write` policy), from the worktree | denied | written |
| the same from the main checkout, into its own `.git/` | denied | written |
| a `SessionStart` hook of `codex exec -s workspace-write`, with a model id the ChatGPT plan refuses before the turn | written | — |

Codex runs hooks outside its sandbox, so its run state was never at risk: its
sandbox denies even a plain checkout's `.git` to the worker's commands, and the
codex delegate passed in a plain checkout on 2026-10-22. No other backend's
sandbox starts (agy, opencode, Copilot, Cursor, Claude Code; see their
reference files), so Grok is the only backend that hit this.

## What changed

A git path outside the work tree (a linked worktree, a submodule) now puts the
state in `/tmp/crew-state-<uid>/<12 hex of the sha256 of the real git
path>/crew`. `/tmp` is shared, so the top dir is created 0700; a link or
another user's directory in its place is refused, and one of this user's with
wider modes is narrowed to 0700. This machine had one at 0775 before the batch,
most likely from the hand-patched copy used in those sessions; the first
0.15.2 run narrowed it. A plain checkout keeps `.git/crew`.

`--self-test` builds a linked worktree inside the main checkout and checks that
the plain checkout keeps the git dir, where the worktree's state goes, the 0700
mode, one dir per worktree, the guard denying the worker its run dir, the
narrowing, and the refusal of a link: 9 new checks, 438 in all. With 0.15.1's
`state_base` it fails at the worktree check.

## Not run live

A codex delegate in a worktree (the probes settle where its hooks run), and the
other backends in one.
