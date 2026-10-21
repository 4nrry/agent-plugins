# Batch 2026-10-13-lab-and-smoke — claims

**Lab and smoke notes, not run records.** Imported from the crew README
(0.3.0–0.4.2). n=1 per case, throwaway repos, lab notes kept in session
scratchpads and not committed. They explain why each check in `crew.py`
exists; they support no comparison with Claude doing the same work — no
quality, time or cost claim.

## agy 1.3.4 lab (`gemini-3.8-flash-low`)

| Observed | Consequence in the script |
|---|---|
| Workspace hooks fire in `-p`: all six events | the guard can be agy's own hooks |
| A `PreToolUse` that prints `{}` denies the call | every handler prints an explicit decision, also when it breaks |
| `--sandbox` did not stop writes outside the workspace | path and scope guards are the only limit |
| Without `--dangerously-skip-permissions`, `run_command` is auto-denied (10 config variants) | delegate uses skip-permissions plus hooks |
| Impossible `--json-schema`: exit 0, `SUCCESS`, `structured_output: null` | null structured output is a failure |
| `--print-timeout` hit: exit 0 with partial output; one stderr line | that marker is a failure |
| Headless denied action: exit 0, `denied_actions` in the envelope | failure in delegate, warning in review |
| `--mode plan` stopped the requested write | review uses plan mode |
| `--agent` not discovered in five layouts | no custom agents |
| `-p "/usage"` answers with `num_turns: 0` and per-group remaining fraction | the quota preflight |
| Long `run_command` goes to a background task after ~4 s whatever `WaitMsBeforeAsync` says; agy then waited 16 and 11 min for orphaned `nx`/`npm` | the background watcher |

From the prototype on a real port (Nest to TanStack Start): pushed on, Gemini
searched for the gate in `~/.claude`, `/tmp`, `ps` and `../`; "fixed" an
`nx.json` Nx writes itself; reported no divergence unasked; skipped formatting
without a formatter in the gate; invented an alias.

## Smoke runs

agy 1.3.4: delegate `slugify` + 3 tests `ok` in 43 s (Stop came with
`TERMINAL_STEP_TYPE`, not `NO_TOOL_CALL`); a check failing once first exposed a
cache of red gates (fixed to cache green only), then `ok` in 61 s; review `ok`
in 21 s with 5 findings. agy 1.4.2 (2026-10-18): the same behaviors held;
Argon `ok` in 66 s once `__pycache__/` was ignored.

opencode 1.19.0 (`longcat-2.5-preview-free`): `slugify` `ok` in 50 s; a red
then green gate `ok` in 68 s via `run -s`; a redirect to a file and the follow-up
`write` both denied; `$schema` written into `opencode.json` before the snapshot
(fixed: preflight in a temp dir). Lab: an open stdin hangs `opencode run`;
`permission.bash: deny` makes free models fail at start (403). Quality bench
(n=1, a 16-case CJS service port): longcat, space-bunny and muse-spark passed;
longcat kept the 22 assertions one by one and was slowest (139 s vs 34 s).

copilot 1.0.96 (Free, `auto` served gpt-5.6-luna): delegate with a once-failing
check `ok` in 21 s, 0.529 AI credits; review `ok` in 19 s, 0.411 credits, one
correct finding. Lab: exit 0 on failed tasks; hooks load only with
`COPILOT_ALLOW_ALL=true`; hook timeouts fail open; excluding only `bash` caused
2,826 `task` calls and ~5.5 credits; `--max-ai-credits` below 30 is refused;
`--model X` refused for all 32 catalog models on Free.

## Not measured

Comparison with Claude on the same slice; false-positive and false-negative
rates of the guards; parallel runs in worktrees; the cause of hooks that do not
load; Claude or GPT models through agy (quota was empty).
