# Batch 2026-10-25-claude-delegate — claims

**Lab and smoke notes, not run records.** Claude Code 2.1.310; n=1 per case,
throwaway repos, run with `env -i` (HOME, PATH, USER, LANG) so no Claude host
variable reached crew or the worker. Logs stayed in the session scratchpad and
were not committed.

## Lab (hooks in a `--settings` file, `-p --restricted`, haiku)

| Observed | Consequence in the script |
|---|---|
| SessionStart, PreToolUse and Stop fire; `CREW_RUN` reaches the hooks | `cl-start` proves they loaded |
| PreToolUse `permissionDecision: "deny"` stopped `printf hi > hello.txt`; an explicit `"allow"` ran `ls` under `acceptEdits` | `cl-pre` prints allow on every passed call |
| Stop carries `last_assistant_message` and `stop_hook_active`; `decision: "block"` continued the turn | `cl-stop` is cx-stop |
| With the hook allowing everything, `--restricted` still refused Write outside the repo, to `.claude/settings.json` and to `.git/hooks/pre-commit`, and left an empty `.claude/.cc-writes` | crew removes the leftover dirs it created |
| `sandbox.enabled` in `--settings`: every Bash call failed, "apply-seccomp: write /proc/self/setgroups (nested userns is capability-restricted…)" | no sandbox; the verdict warns |

## Smoke

The slugify task from the Codex batch, model `sonnet`.

1. The hooks never ran: `cl-*` was missing from the `hook` subcommand's
   choices, argparse exited 2, and Claude read exit 2 as a block, so even Read
   was denied. Fixed; the self-test now runs the real hook process.
2. ok in 20 s ($0.04), but two Stops asked for the report: the prompt did not
   carry the report schema. Fixed in `report_rule`.
3. ok in 21 s ($0.038, 8 turns): one Stop, gate green on the first try, no
   denials, report `done` with no divergences, nothing left in the repo. The
   diff matched the brief, `import re` at module level.

From inside Claude Code (no `env -i`) the run is refused before the worker
starts.
