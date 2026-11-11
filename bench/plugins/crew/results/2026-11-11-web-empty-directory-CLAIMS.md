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
worker's `PWD` is that directory and `OLDPWD` is dropped. A file written
there fails the run, as a changed work tree does under `--cwd`. claude, grok
and hermes are unchanged: they lose their file tools. The verdict's
`read_only` says the run was in a new empty directory.

**A first design was dropped after a cold review.** It used one shared
directory under `/tmp/crew-state-<uid>`. The reviewer showed, with stand-in
binaries, that the worker still received the repository path (the schema path
in agy's arguments, `OPENCODE_CONFIG_DIR`, `PWD`), that the directory's parent
holds the run records of linked worktrees, that a file one worker left stayed
for the next ones while the verdict still said "empty", and that eight
overlapping runs all reported one worker's write.

**Checked with a stand-in CLI, no model run.** `crew.py --self-test`, 451
checks, on 2026-11-11; nine are for this change. A stand-in `agy` that
answers with its directory, its listing, `PWD`, `OLDPWD` and its arguments
showed: a directory under `crew-web-<uid>` ending in `cwd`, empty; no
repository path in `PWD` or the arguments, `OLDPWD` unset; the schema file
outside the repository's state; the directory gone after the run; the
repository as the directory without `--web`. A file the stand-in wrote
failed the run and left the repository untouched. A day-old directory beside
the run's was removed and a fresh one kept. A link in place of
`crew-web-<uid>` was refused before any run directory was made.
`backends.py --self-test` checks that the three backends are agy, opencode
and codex.

**Not measured.** No worker CLI was run for this change. Whether a second
turn (`--session`) finds its conversation when each turn has a new directory:
agent-fleet's workers never use sessions, and its 2026-10-22 record has agy
and opencode answering single turns from a temporary directory of their own
that held only their prompt and schema files. What agy and codex can read by
absolute path from there. That opencode's `external_directory: deny` stops
every path outside the directory comes from its config, not from a run here.
Environment variables other than `PWD` and `OLDPWD` are inherited as before.
