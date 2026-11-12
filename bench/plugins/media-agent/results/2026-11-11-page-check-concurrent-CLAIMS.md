# Batch 2026-11-11-page-check-concurrent — claims

**Notes, not run records.** Why media-agent 0.21.1 changes the last check of
`skills/page-check/scripts/page-check.mjs --self-test`. Measured on
2026-11-11 with Node 26.13.1 and Google Chrome 157.0.8103.78 on Linux, one
machine. Nothing here compares an agent with and without the skill.

**The failure.** The last check listed every name starting with `page-check-`
in the system temporary directory before and after the run and took each new
one for its own leftover. Two self-tests running at once on one machine (two
worktrees, or two CI jobs on one runner) each saw the other's directories.
With the 0.21.0 script, two rounds of two self-tests started together: in
each round one of the two failed with `a temporary directory was left`,
naming the other process's Chrome profile (`page-check-dsVZs5`) in one round
and its test directory (`page-check-test-vvvmZu`) in the other. 2 failures in
4 runs. Each passes when run alone.

**The change.** The self-test now makes a private parent directory
(`page-check-run-*`) and points `TMPDIR`, `TMP` and `TEMP` at it for the
length of the run, so its own test directory, each profile directory that
`launch()` makes, and whatever a child process it spawns (the `--help` run)
writes to its temporary directory all land there. The last check fails if
that parent holds anything but the test directory; then the parent is
removed and the variables are restored. Directories other processes make in
the system temporary directory are no longer looked at.

**Concurrent runs.** Six rounds of two self-tests of the 0.21.1 script
started together: 12 of 12 runs passed with 45 of 45 checks, and no
`page-check-*` name was left in the system temporary directory afterwards. A
single run alone took 71 s.

**A real leak is still caught.** Two scratch copies of the 0.21.1 script, each
with one leak planted, run alone:

- `launch()` no longer removes its profile directory: exit 1, `1 of 45
  failed`, the check named the nine profile directories the run had left.
- the `--help` child process makes a `page-check-child-*` directory in its
  temporary directory and leaves it: exit 1, `1 of 45 failed`, the check named
  that directory.

In both, nothing was left in the system temporary directory after the run:
the private parent is removed at the end whatever the check found. The
removal swallows its own errors, so a directory it fails to remove stays
without a message.

- After a cold review, Chrome is given its per-launch temporary directory in
  `TMP` and `TEMP` as well as `TMPDIR` (Chrome on Windows reads the first
  two), and the parent is made and removed by a wrapper around the whole
  self-test, so an early failure no longer leaves it or the changed variables
  behind. The concurrent rounds and planted leaks above ran before this
  change; `just check` ran after it.
- Not measured: macOS and Windows (on Windows `os.tmpdir()` reads `TEMP` and
  `TMP`, which are set; not run there), a leak by a process that resolves its
  temporary directory without reading these variables, and a leak inside the
  self-test's own test directory, which is removed with the parent unseen.
