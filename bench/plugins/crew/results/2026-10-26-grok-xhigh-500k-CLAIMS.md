# Batch 2026-10-26-grok-xhigh-500k — claims

**Smoke notes, not run records.** The user's choice: Grok runs as grok-4.7
at xhigh with the 500k window, never a fast variant. n=1 per case.

| Where | How the default is set | Check |
|---|---|---|
| Grok Build 1.0.70 | every tier `grok-4.7` at `xhigh`; delegate passes `--reasoning-effort xhigh` when the task names none; 500k from `[model."grok-4.7"] context_window = 500000` in `~/.grok/config.toml`, added on this machine (backup next to it) | two-turn ask ok (19 s); slugify delegate ok in 108 s, report `done`, one MCP call denied |
| Hermes 0.22.5 | every tier `xai-oauth:grok-4.7` at `xhigh`; Hermes already reads `context_length: 500000` for grok-4.7 from api.x.ai (its endpoint metadata cache) | two-turn ask ok (6.5 s) |
| cursor-agent 2026.10.22 | every tier and the delegate default `grok-4.7[context=500k,reasoning_effort=xhigh,fast=false]` | two-turn ask ok (12.5 s); slugify delegate ok in 62 s, report `done` |

Every diff matched the brief. Trust entries the runs added were removed.
