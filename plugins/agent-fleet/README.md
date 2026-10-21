# agent-fleet

Rules for multi-agent work: routing each phase to the right model, sizing a
fan-out, constraining output schemas, and verifying what agents return with a
bundled citation checker (`scripts/verify_citations.py`).

```
/plugin install agent-fleet@4nrry
```

## What it ships

| Component | Path | What it does |
|---|---|---|
| Skill | `SKILL.md` | The rules themselves — read before a fan-out, and again when results come back |
| Injection hook | `hooks/inject.sh` | `UserPromptSubmit`: puts the skill in context on a matching prompt |
| Routing hook | `hooks/check-routing.sh` | `PreToolUse` on `Workflow`: denies once per unrouted script |
| Workflow | `workflows/deep-research.js` | Deep research with per-phase model overrides |
| Verifier | `scripts/verify_citations.py` | Fetches each cited URL and string-checks the quote |
| CLI worker | `scripts/fleet_worker.py` | Runs the search and fetch-and-extract phases on grok, agy, opencode or hermes, read-only, with the built-in workflow's schemas |

## Breadth on another CLI

`fleet_worker.py` lets any orchestrator with a shell put the deep-research
breadth phases on a different agent CLI: `search` takes the scope's angles and
returns URL-deduplicated sources capped at 15 by relevance, `extract` takes
those sources and returns claims with verbatim quotes. Prompts, schemas, caps
and the dedup key follow Claude Code's built-in workflow (2.1.306); verify and
synthesis stay with the orchestrator.

`search --backend grok,hermes,agy` runs every angle on every engine at once
and merges the results by normalized URL. Each source carries `foundBy`, the
engines that returned it; within a relevance level, a source more engines agree
on is fetched first, and the 15-slot budget runs over the merged set ranked, so
a low result never takes a slot a high one needed. One failed engine costs
coverage, not the run. With several backends, `--model` takes
`backend=model[,backend=model]`.

### Routing by phase

From the smoke runs below — n=1 per cell, so this is where to start, not a
ranking. Re-check after a CLI update; agy moved from 1.4.3 to 1.4.4 during the
day these were taken.

| Phase | Start with | Why | Avoid |
|---|---|---|---|
| Scope | the orchestrator | one agent whose quality shapes every later phase | — |
| Search | `grok,hermes,agy` together | three indexes: xAI (grok, and hermes with `web.search_backend: xai`) and Google through agy; in the merged run, 1 of 11 sources was found by two engines and the rest by one | agy alone: one of its two search runs timed out at 5 min |
| Search, one engine | grok | 13–33 s, closed schema, about $0.01–0.02 | — |
| Fetch and extract | opencode (`minimax-m3.1-flash-free`), grok, or hermes with Firecrawl | 5 of 5 quotes verbatim each; opencode at $0 and 12 s, hermes 12 s | agy: 1 of 4 verbatim; hermes without `web.extract_backend` |
| Verify (3 votes) | the orchestrator's mid-tier subagents | the adversarial pass is where depth pays (agent-fleet rules) | a free breadth model |
| Synthesis | the orchestrator | the rules hand it to you, not to an agent | — |

opencode runs only six free Zen models; any other slug is refused. Terms
from the Zen docs and context windows from models.dev, both read 2026-10-21 —
they change, so re-read them before relying on this table:

| Model | Data terms | Context |
|---|---|---|
| `minimax-m3.1-flash-free` (default) | zero retention, no training | 1M |
| `deepseek-v4.1-flash-free` | zero retention, no training | 200k |
| `glm-5.3-flash-free` | zero retention, no training | 200k |
| `nemotron-3.5-super-vl-free` | logged by NVIDIA to improve its products; no personal or confidential data | 1M |
| `nemotron-3.5-lightning-free` | same as Super VL | 262k |
| `mimo-v2.6-flash-free` | prompts may be used to improve the model while free | 200k |

A model whose terms are not zero-retention puts its terms in the output's
warnings. A 200k window holds one page with room to spare (the longest page
measured, 156k characters, is about 40k tokens); a search loop that fetches
twenty pages is what needs the 1M ones.

hermes for extract needs a page reader: `web.extract_backend: firecrawl` in
`~/.hermes/config.yaml` (keyless, with the free-tier ring as fallback). It
truncates every page to `web.extract_char_limit` characters (default 15000)
keeping head and tail, so a quote from the middle of a long page is gone;
size it to the pages you research.

Each worker runs in an empty temp dir in its backend's read-only mode (grok
`--permission-mode plan`, agy `--mode plan`, hermes `-t web`, opencode with
edit and bash denied through `OPENCODE_CONFIG_CONTENT`), and every string a
page produced is stripped of control, format and bidi code points before it
reaches the orchestrator. Exit 0 is never read as success.

The offline `--self-test` covers parsing, schema checks, dedup and command
construction. `TESTED` lists the phases each backend version completed in a
smoke run; anything else carries a warning in the output.

### Smoke runs (2026-10-21)

One public question, one angle for `search`, then one shared source for
`extract`; quotes string-checked with `verify_citations.py` against an archive
copy, because the source host answers scripted GETs with 403. n=1 per cell,
not a bench record: read it as "this ran", not as a quality ranking.

| Backend (model) | search | extract | Verbatim quotes |
|---|---|---|---|
| grok 1.0.62 (default) | ok, 25–33 s, ~$0.02 | ok, 65 s | 5 of 5 |
| opencode 2.1.1 (`longcat-2.5-preview-free`, since dropped from the allowlist) | **failed twice**: exit 1 after ~280 s with a valid result in its last message, cause not found | ok, 26 s, $0 | 5 of 5 |
| opencode 2.1.2 (`minimax-m3.1-flash-free`) | not run | ok, 12 s, $0, one `webfetch` | 5 of 5 |
| hermes 0.22.2 (`claude-sonnet-5-5`, its default) | ok, 45 s, $0.04 | no claims: needs `web.extract_backend` (firecrawl, tavily, exa…) to read a page | — |
| hermes 0.22.2, `web.extract_backend: firecrawl`, `extract_char_limit: 50000` | — | ok, 12 s, $0.04 | 5 of 5 |
| agy 1.4.3 (`gemini-3.8-flash-medium`) | **failed**: its `search_web` returned no summary and the run hit the 5 min print timeout | ok, 236 s | 1 of 4 |
| agy 1.4.4 (same model) | ok, 112 s, 5 results (in the multi-engine run) | — | — |

Multi-engine run, `--backend grok,hermes,agy`, same angle: 3 of 3 engines
ok, 11 merged sources from 12 results, one of them (`nma.gov.au/…/founding-of-canberra`)
found by both hermes and agy.

What the first runs broke, now fixed and covered by the self-test:

- opencode 2.1.1 added `execute`, a JS sandbox with `fetch()`; with bash
  denied a free model reached for it six times. Denied now, with `task`.
- opencode 2.1.1 ends a good run on the final text event, with no
  `step_finish reason=stop` after it, which 1.x always sent.
- grok loads `~/.grok/rules/` and the user's MCP servers even in plan mode.
  With MCP denied, a memory rule there left it returning claim and quote
  `"placeholder"`. The worker now allowlists `web_search,web_fetch`, turns
  memory and the Claude/Cursor rule scans off, appends a rule saying the
  others do not apply, and fails any quote under 20 characters.

## Why the trigger is a hook and not a description

The skill's own description almost never fires it. Over 20 frozen queries run 3
times each, the shipped description fired on **2 of 30** should-trigger runs
(per-query recall 0.00–0.33), and four optimizer rewrites never moved the
held-out score — while all five descriptions stayed silent on **all 150**
should-not runs. Triggering is therefore mechanical, not persuasive. Raw harness
output, eval set and the full reading:
[`2026-08-06-trigger-eval/`](../../bench/plugins/agent-fleet/results/2026-08-06-trigger-eval/).

So a `UserPromptSubmit` hook injects the skill whenever the prompt **contains**
`ultracode` or `deep-research`. It is a substring match, so it fires on a prompt
that merely mentions them as readily as on one that asks for a fan-out —
measured 2026-08-20: **4 of 4** invocations and **8 of 8** mere mentions, at
10 KB of injected context per fire. That batch also shows what the swap did not
buy: run against the older eval, the hook fires on 1 of its 10 should-trigger
queries, because those test relevance the user never names and a substring match
cannot reach. The hook made explicit invocation reliable; it did not close the
gap the description left.
[`2026-08-20-hook-grep-CLAIMS.md`](../../bench/plugins/agent-fleet/results/2026-08-20-hook-grep-CLAIMS.md).

## Why the routing check is a hook too

Same reason, one level up. A predefined deep-research run reached ~97 agents all
inheriting the session's top-tier model with the rule loaded in context — the
prose rule was there and did not fire. `hooks/check-routing.sh` denies a
`Workflow` call once per distinct unrouted script, with the routing instruction
as the reason; re-invoking unchanged passes, because re-invoking after reading
the reason is the acknowledgment.

## Provenance of the rules

The rules in the skill body come from paired A/B runs made while developing it.
Those predate this repository's protocol and are not published as records here,
so read them as design notes rather than as measurements you can check. What
*is* checkable lives under
[`bench/plugins/agent-fleet/`](../../bench/plugins/agent-fleet/), per
[`bench/PROTOCOL.md`](../../bench/PROTOCOL.md).
