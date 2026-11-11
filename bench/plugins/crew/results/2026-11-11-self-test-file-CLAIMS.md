# Batch 2026-11-11-self-test-file — claims

**Notes, not run records.** Why crew 0.15.6 moves the self-test out of
`crew.py`. extension-audit 0.2.0's audit of crew
(`bench/plugins/extension-audit/results/2026-11-10-three-audits-CLAIMS.md`)
noted that the file sat a few KB under 256 KiB (262,144 bytes), the size
above which the claude.ai plugin directory holds a file for human review.

**Sizes, 2026-11-11.** `crew.py` was 257,395 bytes, 4,749 under the limit.
Its `self_test()` was 1,126 lines of it. After the move `crew.py` is 176,287
bytes and the new `crew_selftest.py` 83,053.

**How it was moved.** By a script working on the syntax tree, not by hand:
it put `crew.` before each of the 286 uses of a name that `crew.py` defines
at top level (98 distinct names, `__file__` among them), dropped the two
`global` lines, and would have stopped on any local that shadowed such a
name; none did. Apart from that prefix the 1,124 moved lines are the same
text. Three imports the move left unused in `crew.py` were removed
(`pathlib` was already unused).

**Checked.** `crew.py --self-test` and running `crew_selftest.py` both give
442 checks ok, the number before the move. A name check over both files
found nothing undefined and no unused import. `just check` passes.

**Not measured.** Whether the directory's reviewers count a test file the
same way. The self-test now runs against a second import of `crew` when it
is started through `crew.py`; nothing in it depends on being the main
module, but only the 442 checks say so.
