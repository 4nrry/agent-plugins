# Batch 2026-11-09-grok-headless-trust — claims

**Lab and smoke notes, not run records.** Grok Build 1.0.77, plus the 1.0.70
binary still in `~/.grok/downloads`; the live run on crew 0.15.3 with grok-4.7
at crew's default effort (medium); n=1 per case unless a case says otherwise.
Throwaway repos outside /tmp, untrusted in Grok except where a case says so;
after the batch `~/.grok/trusted_folders.toml` was byte-identical to its
backup. Logs stayed in the session scratchpad and were not committed.

## The question

crew up to 0.15.2 refused a repo Grok does not trust. The reason came from the
2026-10-22 lab on 1.0.67: global hooks were "listed only in a trusted folder",
which is `grok inspect`'s listing, not a headless run. Grok's 1.0.77 hooks
guide says a headless run (`grok -p`) counts the folder as trusted for the
user's own hooks, while the repo's own hooks still need trust.

## Probe (no model turn)

A user hook in `~/.grok/hooks/` and a project hook in the repo's
`.grok/hooks/`, both logging each event they get and doing nothing in a session
without the probe's id in its environment. `grok -p` with crew's delegate flags
and a model id that does not exist, which fails before any request.

| Case | `grok inspect` | User hook fired | Project hook fired |
|---|---|---|---|
| untrusted, 1.0.77 (twice, before and after the trusted case) | `projectTrusted: false`, plugin hooks only | `SessionEnd`, `Stop` | nothing |
| trusted, 1.0.77 | `projectTrusted: true`, user and project hooks | `SessionEnd`, `Stop` | `SessionEnd` |
| untrusted, 1.0.70 | `projectTrusted: false` | `SessionEnd`, `Stop` | nothing |

`SessionStart` fired in no case, trusted or not: the unknown model fails before
it. The probe shows the user's hook file loading without trust while trust
still holds the repo's hooks back; the live run below covers SessionStart, the
guard and the gate. `grok inspect` lists no user hook in an untrusted folder on
either binary, so it does not tell what a headless run loads.

## What trust still changes

The same probe with an `AGENTS.md` and a `CLAUDE.md` at the repo root: the
headless start was not refused, and the session's `prompt_context.json` listed
the two only when the repo was trusted. The user's own `~/.claude/CLAUDE.md`
and `~/.grok/rules/` were listed in both cases. Grok's project-rules guide
says so too: loading project rules at startup needs folder trust. In an
untrusted repo the worker runs without the repo's instructions, and without
its skills, MCP servers and hooks.

## Live run

| Case | crew | Result |
|---|---|---|
| the slugify delegate of the 2026-11-09-grok-worktree-state batch (same files and brief, which asks for one write outside scope first), in a plain checkout Grok does not trust, with an `AGENTS.md` at its root | 0.15.3 | `ok` in 122 s: SessionStart logged, the MCP call and the out-of-scope `NOTES.md` write denied, gate green at the first Stop, report `done`, hook file removed; one warning, that the worker does not read `AGENTS.md`, and the session's `prompt_context.json` lists only the user's own instruction files |

The diff matched the brief (`import re` at module level, `slugify` below
`title_words`, three tests, `TitleWordsTest` untouched).

## What changed

`preflight_grok` no longer refuses an untrusted repo. When Grok does not trust
it and the repo root has instruction files Grok would read (the names in its
project-rules guide, `.claude/CLAUDE.md`, and `.md` files in `.grok/rules`,
`.claude/rules` or `.cursor/rules`), the verdict warns that the worker does not
read them and how to trust the repo. `--self-test` runs the preflight against a
fake `grok`: no refusal and no warning without instruction files, a warning
naming them, none when trusted, and the version warning; 4 new checks, 442 in
all. With the old refusal back it fails at the first of them.

## Not run live

1.0.67, whose binary is gone. A trusted repo on 0.15.3: the preflight there
only lost a refusal it never raised, and the 1.0.77 batch covers that path.
