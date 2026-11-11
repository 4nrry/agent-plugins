# Batch 2026-11-11-agy-delegate-1.5.6 — claims

**Smoke notes, not run records.** The `delegate` cases that
`2026-11-11-agy-review-delegate-CLAIMS.md` left unmeasured on agy 1.5, and
why crew 0.16.4 names 1.5.6 as the agy it was exercised on. 2026-11-11, agy
1.5.6, gemini-3.8-flash-high, agy's own login, a throwaway repository of four
files; scope `calc.py` and `test_calc.py`, gate `python3 -m unittest -q`;
n=1 per case, 5 worker calls through crew 0.16.3. Every task asked for the
same change (a `spread()` function and two tests) plus the instruction in
the first column. Times are agy's wall time as crew measured it.

| Instruction | Result |
|---|---|
| start `sleep 600` and leave it running, then finish | ok in 146 s. The command ran as a child of agy with the run's mark. agy printed "terminating 1 daemon task(s) on exit" and exited in the second its `Stop` hook answered; no `sleep 600` was left. `agy.background_killed` empty: crew's watcher, which waits 15 s, had nothing to stop. One guard denial, a `ls -la .agents` |
| run `sleep 45` first, with `timeout` 25 s | failed in 29 s, exit 1. agy exited 3, envelope status `ERROR`, `AGY_ERROR` with `"reason":"print_timeout"`, and said it terminated the running `sleep 45`. Five failures in the verdict: the exit code, the timeout marker, the status, the null report, and the final gate (no file in the scope changed). The hooks file was removed |
| end with plain text, do not call `finish` on your own initiative | ok in 73 s: the worker called `finish` all the same; gate green at `finish` and at `Stop` |
| never call `finish`, even if asked | failed in 64 s, exit 1. The run took four turns, each answering "done, no report", then one `Stop` with `terminationReason` `MAX_FORCED_INVOCATIONS`; rc 0, status `SUCCESS`, `structured_output` null. One failure: the null report. The gate ran after agy and passed; both files were changed |
| call `finish` before reading or editing anything | ok in 65 s. The first `finish` was denied with "The gate FAILED (attempt 1 of 3)" and the gate's output; the worker made the change; the second `finish` was allowed on a green gate, and `Stop` came with `TERMINAL_STEP_TYPE` |

agy's reported token totals for the five: 91,800, 17,266, 59,354, 51,254 and
45,966.

**Against what crew's code records of earlier agy.** A print timeout exits 3
with status `ERROR` (1.3.4: exit 0), and agy ended the command it left
running, at the timeout and at the normal exit (1.3.4 waited for such
commands, 11 and 16 minutes in two runs; 1.4.2 logged a 15 minute wait).
With `--json-schema` and no `finish` call, the run went on for three more
turns before `Stop`; what agy sent the model in them is not in the logs, so
that it asked for the report is inferred from the stop reason.

**What changed in crew 0.16.4.** `TESTED_AGY_VERSION` is 1.5.6, so the
version warning is gone on that agy and back on any other. The timeout
failure says "agy exits 0 anyway" only when it did, and the null-report
failure says "agy returns status SUCCESS anyway" only when the status was
`SUCCESS`. `crew.py --self-test`: 510 checks, one new (an envelope like the
timeout run's gives the exit code, the timeout, the status and "no report
came back", and neither of the two "anyway" phrases).

**Not measured on 1.5.6.** A `Stop` with `NO_TOOL_CALL`, and with it crew's
own request for a missing report (`AGY_REPORT_ASKS`): agy's forced
invocations came first. A `Stop` answered `continue` after a red gate.
Whether agy honours a `continue` after `MAX_FORCED_INVOCATIONS`; crew
answers `stop` there. The watcher stopping a command, which needs an agy
that waits. `ask` on 1.5.6. Models other than Flash.
