# Batch 2026-11-11-web-empty-directory — claims

**Notes, not run records.** Why crew 0.16.0 runs a `--web` ask on agy,
opencode and codex in a directory of its own. The 0.2.0 audit found that
`--web` was documented as web-only on six backends while three of them keep
their file tools: agy ignores the flag, codex only gains `--search`, and
opencode's web profile keeps read, grep, glob and list. 0.15.4 said so in the
docs and in the verdict; 0.16.0 takes the repository out from under the
worker instead.

**What changed.** For those three, `ask --web` runs the CLI in
`/tmp/crew-state-<uid>/web-cwd` (mode 0700, one path for every run) and not
in `--cwd`. claude, grok and hermes are unchanged: they lose their file tools.
The verdict's `read_only` names the empty directory.

**Checked with a fake CLI, no model run.** `crew.py --self-test`, 447 checks,
on 2026-11-11. A stand-in `agy` that answers with its working directory
reported the empty directory with `--web` and the repository without it. An
entry older than a day was removed and a fresh one kept. A file the stand-in
wrote there produced a warning and left the repository untouched. A symlink
in place of the directory was refused before anything ran.

**Earlier live runs from an empty directory.** agent-fleet's `fleet_worker.py`
has passed an empty temporary `--cwd` to `ask --web` since crew 0.11.0; its
2026-10-22 record has agy and opencode answering from one.

**Not measured.** No worker CLI was run for this change. Whether a second
turn (`--session`) finds its conversation on each of the three when both
turns use the shared directory. What each CLI can still read by absolute path
from there: the directory hides the repository, it does not confine the
worker. Codex from an empty directory has no live record here.

**Size.** `crew.py` is 261,682 bytes after this change, 462 under the 256 KiB
above which the claude.ai directory holds a file for review.
