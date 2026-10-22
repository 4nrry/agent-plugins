# Batch 2026-10-22-grok-delegate — claims

**Lab and smoke notes, not run records.** Grok Build 1.0.62, updated to 1.0.67
by itself before the smoke; `grok-4.7-build-fast`, effort `low`; n=1 per case,
throwaway repos. Logs stayed in the session scratchpad and were not committed.
They support no comparison with another worker or with the host doing the
same slice.

## Lab

| Observed | Consequence in the script |
|---|---|
| `GROK_CONFIG` and `GROK_CONFIG_PATH` overlays: hooks absent from `grok inspect` | per-run hooks go in `~/.grok/hooks/crew-<run>.json` |
| Global hooks listed only in a trusted folder (0 in an untrusted one, even ai-memory's) | `preflight_grok` refuses an untrusted repo and says how to trust it |
| A hooks file without `SessionStart` fired nothing; with it, all three events fired | the file always carries SessionStart, which also proves the load |
| `CREW_RUN` from the launching process reaches the hook | handlers act only for this run's id; other sessions get a no-op |
| Tools: `run_terminal_command{command}`, `read_file{target_file}`, `search_replace{file_path,old_string,new_string}`, `list_dir{target_directory}`, `grep{path,pattern}`, `write{file_path,content}` | `GK_TOOLS` translation |
| `--tools` did not remove MCP tools (`ai-memory__memory_handoff_list` still called) | `gk-pre` denies any `server__tool` |
| `permissionDecision: deny` stopped `printf hi > hello.txt`; `Stop` `decision: block` continued the turn | deny and gate loop |
| Two `Stop` events per run; the last has no `last_assistant_message` | that closing Stop is never blocked |

## Smoke

The task from the Codex batch (slugify plus three tests, scope `src/*` and
`tests/*`, unittest gate, `skip` forbidden). Verdict `ok` in 21 s: gate green
at the first Stop, one denial (the ai-memory MCP call), report `done` with no
divergences, hooks file removed after the run. The diff matched the brief.

## Not run live

A failing gate blocking Stop, and the report re-ask; both run in
`--self-test`. The scratch repos' entries in `~/.grok/trusted_folders.toml`
were removed after the runs.
