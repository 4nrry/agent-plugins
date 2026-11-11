# Batch 2026-11-11-web-live-smoke — claims

**Smoke notes, not run records.** The first live runs of `ask --web` after
crew 0.16.0 moved agy, opencode and codex to a new empty directory per turn
(see `2026-11-11-web-empty-directory-CLAIMS.md`, which lists these as not
measured). 2026-11-11, one Linux laptop, from a linked worktree of this
repository; crew tier `cheap`: agy 1.5.5 with gemini-3.8-flash at low, Codex
CLI 0.167.1 with gpt-6-luna at low, opencode 2.2.7 with
`opencode/deepseek-v4.1-flash-free`. n=1 per case, 15 worker calls in all.
No API key was in the environment; each CLI used its own login. Outputs
stayed in the session scratchpad.

**First turn.** The question asked for the working directory, its contents,
one web search and a word to remember.

| Backend | Result |
|---|---|
| codex | ok in 11.9 s: directory `/tmp/crew-web-<uid>/<random>/cwd`, no files, the search answered |
| opencode | ok in 11.4 s: the same kind of directory, no files, the search answered |
| agy | failed in 6.8 s with an empty reply: it tried a shell command for the listing, which its headless mode denies. Asked again without needing a command: ok in 12.4 s, the same kind of directory as its workspace |

No verdict carried the "left files" warning, and `/tmp/crew-web-<uid>` was
empty after every run in this batch.

**Second turn, `--session` with `--web`.** agy (6.1 s) and codex (4.6 s)
returned the word. opencode failed in 0.4 s on 0.16.0: "Location not found:
<the first turn's directory>". With that directory made again by hand,
empty, the same turn passed, although the turn itself ran in another new
directory. 0.16.1 does that itself when it sees the message: a new
three-turn conversation on opencode passed (5.2, 2.7 and 2.9 s), turns two
and three carrying the warning that says so.

**A write, asked for on purpose.** Each backend was told, with `--web`, to
create `probe.txt` with its file tool.

| Backend | Result |
|---|---|
| codex | refused: "the filesystem is read-only" |
| opencode | refused: it has no file-writing tool in this profile |
| agy | wrote it. The verdict warned that a file was left, and it went with the directory |

**agy 1.5.5 and `--mode plan`.** crew passes `--mode plan
--disable-slash-commands`; agy 1.5.5 prints "--mode plan has no effect while
slash command expansion is disabled". Run directly in a scratch directory
with `--mode plan` and without the other flag, it printed no warning and
still wrote the file. So on this version `ask agy` is not read-only for
files, with either flag set; shell commands were denied in both runs. crew
was last tested on agy 1.4.7. 0.16.1 says so in the verdict (`read_only` and
a warning) for agy 1.5 and later; it does not yet stop the write.

**Not measured.** agy or codex opening an absolute path from the empty
directory. opencode's `external_directory: deny`. Two runs of the same CLI
at once (the first turns ran three different CLIs in parallel). `review` and
`delegate` on agy 1.5.5, which go through crew's hooks. Any model but each
backend's cheap tier. Whether agy 1.5.5 has another flag that stops writes.
