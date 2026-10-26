# Batch 2026-10-25-version-retest — claims

**Smoke notes, not run records.** n=1 per case, throwaway repos, default
`cheap` tier for ask and each backend's default model for delegate. Logs
stayed in the session scratchpad and were not committed.

## Two-turn ask (turn 2 resumes the session and must recall turn 1)

| Backend | Version | Result |
|---|---|---|
| agy | 1.4.7 | ok (gemini-3.8-flash) |
| codex | 0.164.0 | ok (gpt-6-luna) |
| claude | 2.1.310 | ok (haiku), run from a clean environment |
| cursor | 2026.10.22-27dcf5f | first run refused: "Do you trust the contents of this directory?"; with `--trust`, ok (auto) |
| grok | 1.0.70 | first run failed: `grok-4.7-build-fast` "unknown model id" (`grok models` lists only `grok-4.7`); on grok-4.7 the word-recall prompt was refused as "storing a code word", and a neutral recall (17+25, then "what number did you give") was ok |
| hermes | 0.22.5 | not tested: xAI answered HTTP 402 `personal-team-blocked:spending-…` on grok-4.7 too, an account limit |

## Slugify delegate

All ok, gate green, report `done` with no divergences, and each diff matched
the brief (`import re` at module level, three tests).

| Backend | Version | Time | Notes |
|---|---|---|---|
| opencode | 2.1.4 | 18 s | deepseek-v4.1-flash-free |
| cursor | 2026.10.22-27dcf5f | 26 s | worker-server and a TypeScript language server left behind, stopped by the run marker |
| grok | 1.0.70 | 51 s | grok-4.7; one MCP call denied (`ai-memory__memory_handoff_list`) |
| agy | 1.4.7 | 85 s | gemini-3.8-flash-high; one `ls -la .agents` denied; the gate ran twice |
| codex | 0.164.0 | 92 s | gpt-6-luna |

Scratch trust entries (Grok's `trusted_folders.toml`, Cursor's
`~/.cursor/projects/*`) were removed after the runs.
