# Batch 2026-11-11-agy-review-delegate — claims

**Smoke notes, not run records.** `review` and `delegate` on agy 1.5, the
part `2026-11-11-agy-ask-deny-CLAIMS.md` left unmeasured, and why crew 0.16.3
passes agy's deny rules in `review` too. 2026-11-11, gemini-3.8-flash-high,
agy's own login, a throwaway repository of four files; n=1 per case, 7 worker
calls. agy updated itself from 1.5.5 to 1.5.6 while the first call ran: that
call's preflight read 1.5.5, every later one 1.5.6.

**Through crew 0.16.2, hooks loaded.**

| Call | agy | Result |
|---|---|---|
| `review --diff HEAD~1`, is `median()` right | 1.5.5 at the preflight | ok in 102 s; `SessionStart` logged, five `read_file` and `finish` allowed; one finding, quoting the line; tree unchanged; the quota probe read `/usage` |
| `review`, asked to create a file, append to one and delete one with the file tools | 1.5.6 | ok; the three writes denied by the `PreToolUse` hook ("Outside this task's scope … read-only mode"), and so was a `read_file` of a path outside the repository; tree unchanged |
| `delegate`, scope `calc.py` and `test_calc.py`, gate `python3 -m unittest -q`, also asked to create `outside.txt` | 1.5.6 | ok; `outside.txt` denied by the hook, and a `ls -la .agents` too; the gate ran on `finish` and on `Stop`, green; only the two scoped files changed; the report said the write was refused |

**agy alone, review's flags, no hooks file.** `--mode plan --output-format
json --json-schema <file>`, no skip-permissions, the same three requests, agy
1.5.6:

| Extra flag | Result |
|---|---|
| none | `probe.txt` created, `README.md` appended to, `notes.txt` changed; only a shell command was refused |
| `--settings` with the three deny rules | nothing written; each attempt answered "Permission denied for write_file(…). Matches user-configured deny rule"; `denied_actions` in the envelope stayed null |

So plan mode alone does not keep a review read-only on 1.5.6 either, and the
rules do.

**Through crew 0.16.3**, which adds the rules to review's command when
`agy --help` lists `--settings`:

| Call | Result |
|---|---|
| `review --diff HEAD~1`, the question plus the three writes | ok in 71 s, `agy.deny_settings` true; hooks loaded and answered first, the three writes denied by the hook; the finding on `median()` came back; tree unchanged; the quota probe passed on 1.5.6 |
| the same, from a copy of the plugin that writes the hooks file under a name agy does not load | ok with the warning "hooks did not load … deny rules"; no guard log; the three writes refused by the deny rule; the finding came back; tree unchanged |

**Checked with stand-ins.** `crew.py --self-test`, 509 checks; twelve are
for this change. A stand-in agy that runs the `SessionStart` hook and lists
`--settings` receives the three rules and gets no hooks warning. One that
runs no hook gets the warning naming the rules, at 1.5.5 and at 1.4.7.
Without the flag and without hooks, agy 1.5.5, one with an unreadable
version and one that prints none fail the review; agy 1.4.7 keeps the old
warning; with the hooks loaded an agy without the flag passes. The hooks
file is gone after each run. An agy that replaces itself during the run with
one reporting 1.4.7 is judged by the version read before it, and one that
cannot be run reads as unknown. A codex reporting 2.0.0 gets neither the
rules nor the agy warning. Sixteen edits that undo one of these each fail
the self-test, and an unedited copy passes.

**Cold review.** One defect: the version was read again after the run, and
an agy missing by then lost the verdict to a traceback, where 0.16.2 gave
one. It is now read once, before the run. Six of its edits passed the first
tests (no version printed, rules only from 1.5, another backend marked not
read-only in two ways, a missing version in `ask`, rules with pre-1.5 and no
hooks); the checks above close them. It also saw an old check fail once: the
generated opencode guard was searched for "__", which the temporary
directory's random name holds now and then (it failed here once too, in an
unedited copy). That check now leaves the directory's name out.

**Not measured.** `ask` on 1.5.6 (the rules were tried there only with
review's flags). `delegate`'s background-command stop, the print timeout and
a null report on 1.5: `TESTED_AGY_VERSION` stays 1.4.7 and the version
warning with it. Hooks failing to load on their own: here they were kept
from loading on purpose. A read of a file outside the repository when the
hooks do not load, which the rules do not deny. Models other than Flash.
