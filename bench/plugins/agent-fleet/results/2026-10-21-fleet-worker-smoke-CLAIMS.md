# Batch 2026-10-21-fleet-worker-smoke — claims

**Smoke notes, not run records.** No record conforms to
`bench/schema/run.schema.json`: no per-agent token split, no hashed prompts,
no paired arms. n=1 per cell. These notes support "this ran", and the bugs
listed below; they support no comparison between backends.

**Setup.** `plugins/agent-fleet/scripts/fleet_worker.py` at the 1.1.0 commit
(historical: the script has changed since). One public question ("When and why
was Canberra chosen as the capital of Australia?"), one angle for `search`,
then one shared source for `extract`. Quotes string-checked with
`verify_citations.py` against a web.archive.org copy, because the source host
answers scripted GETs with 403.

| Backend (model) | search | extract | Verbatim quotes |
|---|---|---|---|
| grok 1.0.62 (default) | ok, 25–33 s, ~$0.02 | ok, 65 s | 5 of 5 |
| opencode 2.1.1 (`longcat-2.5-preview-free`) | failed twice: exit 1 after ~280 s with a valid result in its last message, cause not found | ok, 26 s, $0 | 5 of 5 |
| opencode 2.1.2 (`minimax-m3.1-flash-free`) | not run | ok, 12 s, $0 | 5 of 5 |
| hermes 0.22.2 (`claude-sonnet-5-5`), no extract backend | ok, 45 s, $0.04 | no claims: xAI is search-only | — |
| hermes 0.22.2, `web.extract_backend: firecrawl`, `extract_char_limit: 50000` | — | ok, 12 s, $0.04 | 5 of 5 |
| agy 1.4.3 (`gemini-3.8-flash-medium`) | failed: `search_web` returned no summary, 5 min print timeout | ok, 236 s | 1 of 4 |
| agy 1.4.4 (same) | ok, 112 s, 5 results | — | — |

Multi-engine `search --backend grok,hermes,agy`: 3 of 3 engines ok, 12
results merged into 11 sources, one found by two engines.

**Bugs the first runs found, fixed in the script and covered by its self-test:**

- opencode 2.1.1 added `execute`, a JS sandbox with `fetch()`; with bash
  denied, a free model used it six times. Now denied, with `task`.
- opencode 2.1.1 ends a good run on the final text event, with no
  `step_finish reason=stop` after it.
- grok loads `~/.grok/rules/` and the user's MCP servers in plan mode. With MCP
  denied, a memory rule made it return claim and quote `"placeholder"`.
- agy exits 0 on its print timeout.

**Page length** (14 of 30 source URLs fetched as full text; one topic):
median 11.6k characters, p75 49k, p90 70k, max 156k (Wikipedia); every
non-encyclopedia page ≤ 24k. Basis for hermes `extract_char_limit: 50000`.
