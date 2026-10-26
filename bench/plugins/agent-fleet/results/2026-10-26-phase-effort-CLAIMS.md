# Batch 2026-10-26-phase-effort — claims

**Smoke notes, not run records.** fleet_worker on crew 0.12.3, where crew's
grok and hermes tiers became grok-4.7 at xhigh for general work. fleet_worker
now runs search and extract at low effort; n=1, one question about the
current Python 3.15 maintenance release. Logs stayed in the session
scratchpad and were not committed.

| Phase | Backends | Effort seen in crew's verdicts | Result |
|---|---|---|---|
| search, 2 angles | grok (grok-4.7), hermes (xai-oauth:grok-4.7), agy (gemini-3.8-flash) | low on every run | 5/6 ok in 63 s; one Hermes run was cut by its own gateway restarting ("Gateway shutting down") |
| extract, 9 sources | hermes, with Firecrawl as its page reader | low | 7/9 ok in 141 s, 36 claims; one failure was the gateway again ("Gateway draining"), one was two quotes under 20 characters |

`verify_citations.py` on a quotes-only report of the 36 claims: 16 quotes
long enough to score, 13 found, 3 partial, 0 absent, 0 on the wrong source.
Run on the raw `claims.json` instead, it also scored every other quoted string
in the file (the web note, titles) and reported 27 absent, so feed it the
quotes, not the JSON.
