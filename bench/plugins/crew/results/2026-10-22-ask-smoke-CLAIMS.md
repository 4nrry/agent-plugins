# Batch 2026-10-22-ask-smoke — claims

**Smoke notes, not run records.** n=1 per backend. Two turns of `crew.py ask`
in a throwaway one-file repo (`calc.py` defining `add`), tier `cheap`. Turn 1:
"Read calc.py and reply with only the name of the function it defines." Turn 2,
with `--session` from turn 1: "What name did you reply in your previous turn?"
Verdicts and logs stayed in the session scratchpad and were not committed.
They show that the argv, the parser and session resume work. They do not
establish answer quality, cost or speed.

| Backend | Version | Model, effort | Turn 1 | Turn 2 (resumed) | Seconds |
|---|---|---|---|---|---|
| claude | 2.1.307 | haiku, low | `add` | `add` | 6.9, 5.5 |
| agy | 1.4.4 | gemini-3.8-flash-low | `add` | `add` | 128.0, 5.8 |
| opencode | 2.1.2 | minimax-m3.1-flash-free | `add` | `add` | 9.5, 3.5 |
| grok | 1.0.62 | grok-4.7-build-fast, low | `add` | `add` | 12.3, 7.8 |
| codex | 0.163.0 | gpt-6-luna, low | `add` | `add` | 7.9, 5.2 |
| hermes | 0.22.4 | xai-oauth grok-4.7-build-fast, low | "file tools aren't available" (expected: `-t web`) | said it named nothing (consistent) | 66.9, 6.5 |

Every work tree was unchanged after the run.

## What the runs changed in the script

- Claude: `--tools Read,Grep,Glob --setting-sources project,local` cut a
  haiku turn from $0.18 to $0.016. Most of the 44,918 cache-creation tokens
  were the user's plugins, hooks and tool schemas. `--bare` is not usable:
  it reads no OAuth login.
- Grok: `--output-format json` returns the run's joined text, which began
  with what `~/.grok/rules/ai-memory-handoff.md` made it say ("I'll check the
  session handoff"). No flag skips `~/.grok/rules/`, so the parser reads
  `streaming-messages-json` and keeps the last assistant message.
- Codex: `exec resume` takes no `-s`, so `sandbox_mode="read-only"` goes in
  through `-c` on every turn.
- One run left 3 processes behind; `stop_run_procs` found them by the
  `CREW_RUN` marker and stopped them.

## Not run

Copilot (each run spends AI credits), Cursor (its login came from an
accidental browser sign-in during a TUI probe), Muse (not logged in) and Kimi
(the plan has no Kimi Code access: 403). Their argv come from `--help`, and
the parser for Cursor, Muse and Kimi is generic.
