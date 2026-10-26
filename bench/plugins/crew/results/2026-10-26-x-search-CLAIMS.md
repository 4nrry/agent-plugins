# Batch 2026-10-26-x-search — claims

**Smoke notes, not run records.** n=1 per backend.

- Grok Build 1.0.70 listed `x_semantic_search`, `x_keyword_search`,
  `x_user_search` and `x_thread_fetch` among its tools. crew's `--web` profile
  allowed only `web_search,web_fetch`, so research workers could not read X.
  Hermes 0.22.5 lists an `x_search` toolset, enabled, that crew's `-t web` left
  out.
- After adding them, `crew.py ask grok --web` and `ask hermes --web`, asked for
  the latest post of the official @xai account through X search, both returned
  the same post (2026-10-22, @SpaceXSI, with its x.com status URL). Grok took
  93 s and Hermes 243 s at crew's default xhigh; fleet_worker runs search at
  low effort.
