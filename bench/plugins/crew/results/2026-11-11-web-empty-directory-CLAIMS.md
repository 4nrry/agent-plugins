# Batch 2026-11-11-web-empty-directory — claims

**Notes, not run records.** Why crew 0.16.0 runs a `--web` ask on agy,
opencode and codex in a new empty directory. extension-audit 0.2.0's audit of
crew (`bench/plugins/extension-audit/results/2026-11-10-three-audits-CLAIMS.md`)
found that `--web` was documented as web-only on six backends while three of
them keep their file tools: agy ignores the flag, codex only gains
`--search`, and opencode's web profile keeps read, grep, glob and list.
0.15.4 said so in the docs and in the verdict; 0.16.0 takes the repository
out from under the worker instead.

**What changed.** For those three, each `ask --web` turn runs the CLI in
`/tmp/crew-web-<uid>/<random>/cwd`, created for the run and removed after it.
The schema file and opencode's web config, which the worker is pointed at, go
in `<random>/run` and no longer in the repository's own crew state. The
worker's `PWD` is that directory and `OLDPWD` is dropped. A file the worker
left there, or beside it, is a warning in the verdict; it is not a failure
because no run here has shown what each CLI leaves in its working directory
on a normal turn. `ask` now traps SIGTERM and SIGHUP, so a stopped run still
removes its directory. claude, grok and hermes are unchanged: they lose their
file tools. The verdict's `read_only` says the run was in a new empty
directory.

**A first design was dropped after a cold review.** It used one shared
directory under `/tmp/crew-state-<uid>`. The reviewer showed, with stand-in
binaries, that the worker still received the repository path (the schema path
in agy's arguments, `OPENCODE_CONFIG_DIR`, `PWD`), that the directory's parent
holds the run records of linked worktrees, that a file one worker left stayed
for the next ones while the verdict still said "empty", and that eight
overlapping runs all reported one worker's write.

**Checked with stand-in CLIs, no model run.** `crew.py --self-test`, 456
checks, on 2026-11-11; fourteen are for this change. A stand-in `agy` that
answers with its directory, its listing, the `PWD` and `OLDPWD` it was
started with (read from `/proc`, since a shell rewrites its own `$PWD`) and
its arguments showed: a directory under `crew-web-<uid>` ending in `cwd`,
empty; `PWD` on it, no `OLDPWD`, no repository path in the arguments; the
schema file outside the repository's state; the directory gone after the
run; the repository as the directory without `--web`. Stand-ins for codex
and opencode ran in such a directory too, opencode with its config directory
beside it. Files left in the directory and beside it were reported and the
repository untouched. A stand-in that removed its own directory still got a
verdict. Of three old directories, the one with no live owner was removed
and the one owned by a running process and a fresh one were kept. An error
raised mid-run left no directory behind. A link in place of `crew-web-<uid>`
was refused before any run directory was made. `backends.py --self-test`
checks that the three backends are agy, opencode and codex.

**Do the checks bite.** Seven edits that break one behaviour each (no `PWD`,
`OLDPWD` kept, only agy moved, no cleanup on error, the schema left in the
repository's state, the owner check gone, only `cwd/` listed) each failed
the self-test on the check written for it; an unedited copy passed.

**Two cold reviews.** The first rejected the shared directory, above. The
second, on this design, found the four defects gone and reported: an
unguarded listing that crashed when a worker removed its directory, a sweep
that could remove a run with a `--timeout` over a day, no signal trap in
`ask`, writes beside `cwd/` unseen, and a `PWD` check that passed without the
code it was for. All are fixed here and covered above.

**Not measured.** No worker CLI was run for this change. Whether a second
turn (`--session`) finds its conversation when each turn has a new directory:
agent-fleet's workers never use sessions, and its 2026-10-22 record has agy
and opencode answering single turns from a temporary directory of their own
that held only their prompt and schema files. What agy and codex can read by
absolute path from there. That opencode's `external_directory: deny` stops
every path outside the directory comes from its config, not from a run here.
Environment variables other than `PWD` and `OLDPWD` are inherited as before.
What agy, codex and opencode leave in their working directory on a normal
turn. A worker running beside another can list the other's directory two
levels up; nothing but a schema file and what that worker wrote is there.
