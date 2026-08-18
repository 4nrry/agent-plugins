# Fan-out pilots — 2026-08-18

Four pilot runs measuring how a five-agent fan-out behaves when it acquires a
stateful browser handle, and what mix of source venues a five-angle retrieval
fan-out actually surfaces. Plugin version 1.0.8, orchestrator `claude-opus-5`,
Claude Code 2.1.234.

**These are pilots, not arms, and they support no comparison claim.** The
protocol defines an arm as runs differing in exactly one declared variable.
Every candidate pairing in this batch differs in two:

| candidate pair | variable 1 | variable 2 |
|---|---|---|
| shared-handle vs own-handle | handle acquisition | subagent model (haiku vs sonnet) |
| docker-web vs docker-reddit | retrieval channel (WebFetch vs Chrome) | source population (blogs vs Reddit) |

So each record stands alone, `variable: "none"`, `arm: "pilot"`, `batch_id: null`.

## Measured totals

Collected by `bench/collect.py` from the durable per-agent transcripts, so the
four-way token split is script-measured, not asserted.

| run | output | input_uncached | cache_write | cache_read | tools | wall ms |
|---|---|---|---|---|---|---|
| chrome-handle-shared (haiku) | 10,245 | 348 | 150,445 | 1,620,877 | 38 | 80,725 |
| chrome-handle-own (sonnet) | 28,223 | 80 | 198,862 | 2,285,342 | 40 | 119,837 |
| docker-source-mix-web (haiku) | 21,490 | 1,338 | 156,897 | 1,364,400 | 47 | 118,440 |
| docker-source-mix-reddit (haiku) | 29,596 | 702 | 337,967 | 4,853,642 | 83 | 171,306 |

## Retraction: the "+81.6%" figure

While this work was in progress, the Chrome/Reddit channel was described as
costing **+81.6% tokens** versus the web/blog run. **That figure is withdrawn.**
It was computed from the Agent tool's `subagent_tokens` summary, which is a
blended number and is not any of the four priced fields the schema requires.
Against the collected records the same two runs compare as:

| field | reddit / web |
|---|---|
| output | 1.38x |
| cache_write | 2.15x |
| cache_read | **3.56x** |
| tool_calls | 1.77x |

The blended figure did not merely have the wrong magnitude — it had the wrong
shape. The dominant term is **cache_read**, which is what re-reading a large
accessibility tree into context on every call actually costs. `PROTOCOL.md`
states the reason in advance: "A single total hides exactly the number a
routing decision needs." This batch is that sentence happening.

Even these ratios are **between two pilots that differ in two variables**, so
they describe these two runs and not the channel. A channel claim needs runs
that hold the source population fixed.

## What each record supports

- **chrome-handle-shared** — an existence proof that silent cross-contamination
  occurs under a shared handle: one agent's `navigate` reported success while
  `read_page` returned another agent's page, and the agent attributed that
  page's content to its own URL. Four of five agents received the identical
  tab id. n=1 proves the failure is possible; it measures no rate.
- **chrome-handle-own** — isolation held: five distinct tab ids, requested URL
  equalled read URL five times, zero errors. It does **not** show content
  extraction worked: `max_chars` 3000 truncated before the comment region on
  every agent, so zero comment authors were extracted.
- **docker-source-mix-web** — of 75 URLs the searches returned, 5 belonged to
  either tool's vendor, and **zero** of the 14 fetched sources were a
  practitioner venue (forum, issue tracker, mailing list). No agent consulted
  the vendor's own page on the one question where it is authoritative, and the
  fleet reported Docker's $9 and $15 per-user-per-month figures without the
  annual-commitment qualifier.
- **docker-source-mix-reddit** — 10 thread reads produced 7 distinct threads,
  and one thread was read by 3 agents working 3 different angles, all three
  returning the same author and quote. To a synthesis stage that reads as
  three-source corroboration.

## What none of them support

- Any claim that the plugin improved. No arm pair exists here.
- Any **rate**: every count is n=1. "Contamination can happen" is proven;
  "contamination happens X% of the time" is not.
- Any cost claim about the Chrome channel as such — confounded with source.
- Any claim about tier (haiku vs sonnet): the only pairing that varies model
  also varies handle acquisition.

## Deviations and soft numbers

- Ad-hoc Agent-tool fan-out, not a Workflow: `workflow_run_id` is null and
  there is no `orchestrator_prompt_sha256`, so no pairing can be checked
  mechanically. Orchestrator-context tokens are not captured (standing gap).
- No frozen eval set; `eval_ref` and `eval_sha256` are null.
- **No mechanical verifier ran.** `verifier_self_test` is null and every
  `outcomes` sub-object is tagged `orchestrator_assertion` — counted by the
  orchestrator from each agent's returned report, never string-checked against
  the pages. Under this protocol that is the weaker of the two trust tiers.
- The venue labels in docker-source-mix-web are each agent's **self-report**.
  Three domains they called independent blogs (uptrace.dev, last9.io,
  qovery.com) were separately confirmed to be commercial product sites, so
  `practitioner_venue = 0` is the reliable figure and the blog/commercial
  split is soft.
- The convergence figure in docker-source-mix-reddit is confounded by agent
  deviation: two of five agents ignored the site-wide search URL they were
  given and narrowed to `/r/podman/`, which plausibly drove part of the
  overlap. It is not a clean property of the channel.
- Quotes in the Reddit run were truncated mid-sentence by a 15-word cap in the
  orchestrator's prompt and would fail a string check expecting whole
  sentences. That is an artifact of the instrument, not of the source.
