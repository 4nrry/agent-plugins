# Batch 2026-10-22-fleet-worker-on-crew — claims

**Smoke notes, not run records.** fleet_worker.py rebuilt on crew's `ask --web
--schema` (crew 0.11.0). n=1 per backend, crew tier `cheap`; one angle
("Python 3.14 release date and headline features"), one source for extract.
Outputs stayed in the session scratchpad and were not committed. They show the
single CLI layer works end to end; they do not measure research quality.

## search (`--backend grok,agy,opencode,hermes`, `--max-fetch 3`)

| Backend | Model (crew cheap) | Result |
|---|---|---|
| grok | grok-4.7-build-fast | ok, 6 results |
| agy | gemini-3.8-flash-low | ok, 5 results |
| hermes | xai-oauth grok-4.7-build-fast | ok, 6 results |
| opencode | minimax-m3.1-flash-free, then deepseek-v4.1-flash-free | failed: first "Model unavailable" (minimax left Zen), then exit 1 after its web search was "cancelled" (the reply still carried 6 results) |

Merged: the two top sources were found by grok, agy and hermes alike
(`foundBy`), the next two by two engines each.

## extract (`--backend opencode`, docs.python.org What's New)

ok, 5 claims. verify_citations.py: 4 quotes checked, 3 found verbatim, 1
partial, 0 absent, 0 on the wrong source.

## What the runs changed

- crew's opencode default and `cheap` tier moved from minimax (gone from Zen
  on 2026-10-22) to deepseek-v4.1-flash-free; minimax stays allowed.
- crew's opencode adapter prints warn-level logs, as fleet_worker did, so a
  failed run's stderr is not empty.
- opencode is documented for extract only: its web search is cancelled here.
