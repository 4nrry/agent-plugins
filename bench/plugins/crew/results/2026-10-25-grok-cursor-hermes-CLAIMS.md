# Batch 2026-10-25-grok-cursor-hermes — claims

**Smoke notes, not run records.** After the account moved to the Grok Heavy
plan and every CLI logged in again. Grok Build 1.0.70, cursor-agent
2026.10.22-27dcf5f, Hermes 0.22.5; n=1 per case. Logs stayed in the session
scratchpad and were not committed.

## Grok Build: the 500k window headless

| Tried | Result |
|---|---|
| `-m 'grok-4.7[context_window=500000]'`, `-m 'grok-4.7 500k'`, `-m grok-4.7-500k` | refused: "unknown model id" |
| `GROK_CONFIG='{"model":{"grok-4.7":{"context_window":500000}}}'` | ignored: the session recorded `contextWindowTokens: 256000`; the overlay only accepts `models`, `features`, a narrowed `toolset` and `shell_environment_policy` (bundled docs) |
| `[model."grok-4.7"]` `context_window = 500000` in `~/.grok/config.toml` (backed up, restored after) | the session recorded 500000; nine turns of ~95k characters in one session, then a question about turn 1: the last request carried 268,743 input tokens and answered right |
| one 1 MB `--prompt-file` | not a test: the user message was cut to ~100k characters (61,188 input tokens) |

`grok models` listed only `grok-4.7` before the new login, and `grok-4.7`,
`grok-4.7-build-fast`, `grok-4.6` and `grok-4.5` after it. Two-turn ask ok
on `cheap` (build-fast, low) and `top` (grok-4.7, xhigh).

## Cursor: model strings

| `--model` | Result |
|---|---|
| `grok-4.7[context=500k]`, `grok-4.7[context=500k,effort=low]`, `grok-4.7[context=256k,effort=low]` | refused: "Cannot use this model" |
| `grok-4.7[reasoning_effort=xhigh,context=500k,fast=false]` | refused (parameter order) |
| `grok-4.7[context=500k,reasoning_effort=xhigh,fast=false]` | ok; init reported "Grok 4.7 500K Extra High" |
| `grok-4.7-xhigh` (flat id) | ok |

That matches Cursor staff on the forum: `--model` takes the full variant
string, every parameter in order. crew used to send `model[effort=x]`, which
these models refuse; it now appends the effort to a flat id and passes a
bracket variant as given. Two-turn ask ok both ways.

## Hermes

After its xAI login was renewed, two-turn ask ok on `xai-oauth:grok-4.7` and
on `xai-oauth:grok-4.7-build-fast`. Before, xAI answered HTTP 402
`personal-team-blocked:spending-…`, then 429 with a 0/0 rate limit.
