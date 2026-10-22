# Batch 2026-10-22-codex-delegate — claims

**Lab and smoke notes, not run records.** Codex CLI 0.163.0, `gpt-6-luna`,
effort `low`, n=1 per case, throwaway repos. Logs stayed in the session
scratchpad and were not committed. They support no comparison with another
worker or with the host doing the same slice.

## Lab (hooks passed as `-c hooks.<Event>=...`, `--dangerously-bypass-hook-trust`)

| Observed | Consequence in the script |
|---|---|
| Inline hooks fire in `codex exec`: SessionStart, PreToolUse, Stop | no hooks file in the tree; `cx-start` proves they loaded |
| Shell arrives as `tool_name: "Bash"`, command in `tool_input.command` | translated to `run_command` for decide_pre |
| File edits arrive as `apply_patch` with the patch text in `tool_input.command` | each `*** Add/Update/Delete File:` target goes through the scope check |
| `hookSpecificOutput.permissionDecision: "deny"` stopped a `printf hi > hello.txt` before it ran | the deny shape `cx-pre` prints |
| `Stop` returning `decision: block` continued the turn with the reason as the next prompt; the second Stop carried `stop_hook_active: true` | the gate loop in `cx-stop` |
| The user's MCP servers start too (an Expo server failed auth in stderr) | MCP tools are denied by the hook |

## Smoke

Task: add `slugify` to `src/text.py` and three tests in a new `SlugifyTest`,
scope `src/*` and `tests/*`, gate `python3 -m unittest discover`, `skip`
forbidden. Verdict `ok` in 23 s: the gate passed at the first Stop, no
denials, report `done` with no divergences. The diff matched the brief; the
review found one cheap-model habit, `import re` inside the function.

## Not run live

A failing gate blocking Stop and the report re-ask; both run in
`--self-test`.
