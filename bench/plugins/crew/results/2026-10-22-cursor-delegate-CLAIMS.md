# Batch 2026-10-22-cursor-delegate — claims

**Lab and smoke notes, not run records.** cursor-agent 2026.10.19-6bbf2c4,
model `auto`; n=1 per case, throwaway repos. Logs stayed in the session
scratchpad and were not committed. They support no comparison with another
worker or with the host doing the same slice.

## Lab (project `.cursor/hooks.json`)

| Observed | Consequence in the script |
|---|---|
| `--sandbox enabled` refused to start: "Sandbox mode is enabled but not available on this system… AppArmor" | `--sandbox disabled`; the verdict warns that hooks are the only limit |
| In `-p`, sessionStart, preToolUse, beforeShellExecution and afterFileEdit fired; `stop` and `afterAgentResponse` never fired, and sessionEnd did | gate as an outer loop resuming the chat (opencode's pattern) |
| preToolUse tools and inputs (also from the bundle): `Read{file_path}`, `Write{file_path,content}` (edits too), `Delete{file_path}`, `List{file_path}`, `Grep{pattern,file_path}`, `Shell{command,cwd}` | `CU_TOOLS` translation |
| `{"permission":"deny","agent_message":…}` stopped `printf hi > hello.txt`; the model reported the block | the deny shape `cu-pre` prints |
| `-p --resume <session_id>` answered with the previous turn's context | the gate loop's resume |
| `--trust` leaves `~/.cursor/projects/<path>/.workspace-trusted` | documented; the scratch entries were deleted after the runs |

## Smoke

The slugify task from the Codex batch. Verdict `ok` in 29 s, one run (gate
green on the first try), no denials, 7 tool calls through the guard, report
`done` with no divergences, `.cursor/` removed after. The run left a
`worker-server` and a TypeScript language server behind. They carried
`CREW_RUN`, so crew stopped them and listed them under `warnings`. The diff
matched the brief.

## Not run live

A failing gate resumed with its output; it runs in `--self-test`.
