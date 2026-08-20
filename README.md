# 4nrry's agent plugins

Plugins and skills for AI agents. The skills follow the
[Agent Skills](https://agentskills.io) open standard, so their bodies and
bundled scripts are portable across tools that speak it. The packaging in this
repo — hooks included — targets
[Claude Code](https://code.claude.com/docs/en/plugins), which consumes it as a
plugin marketplace; other formats may join as the collection grows.

## Install (Claude Code)

Add the marketplace, then install a plugin:

```
/plugin marketplace add 4nrry/agent-plugins
/plugin install agent-fleet@4nrry
```

Or paste `4nrry/agent-plugins` into the Claude Desktop **Add marketplace** dialog.

## Plugins

### agent-fleet

Rules for multi-agent work: routing each phase to the right model, sizing a
fan-out, constraining output schemas, and verifying what agents return with a
bundled citation checker (`scripts/verify_citations.py`).

Ships a `UserPromptSubmit` hook that injects the skill whenever the prompt
**contains** `ultracode` or `deep-research`. It is a substring match, so it
fires on a prompt that merely mentions them as readily as on one that asks for
a fan-out — measured 2026-08-20: **4 of 4** invocations and **8 of 8** mere
mentions, at 10 KB of injected context per fire. The hook exists because the
description
alone barely triggers the skill: over 20 frozen queries run 3 times each, the
shipped description fired on **2 of 30** should-trigger runs (per-query recall
0.00–0.33), and four optimizer rewrites never moved the held-out score — while
all five descriptions stayed silent on **all 150** should-not runs. Triggering
is therefore mechanical, not persuasive. Raw harness output, eval set and the
full reading:
[`bench/results/2026-08-06-trigger-eval/`](bench/results/2026-08-06-trigger-eval/).
What the hook that replaced the description does and does not cover is a
separate benchmark:
[`bench/results/2026-08-20-hook-grep-CLAIMS.md`](bench/results/2026-08-20-hook-grep-CLAIMS.md).

The rules in the skill body come from paired A/B runs made while developing it;
those predate this repository's protocol and are not published as records here,
so read them as design notes rather than as measurements you can check.

## Benchmarks

Improvement claims about plugins in this repo are comparisons between run
records committed under [`bench/results/`](bench/results/), collected per
[`bench/PROTOCOL.md`](bench/PROTOCOL.md) — per-agent token splits, resolved
model IDs, paired arms with hash-checked prompts, and outcomes tagged by
source (script measurement vs orchestrator assertion). A claim without
records is marketing and does not belong here.

Records collected before that protocol existed, or by a foreign harness, are
published as raw output with their hashes and are labeled **imported** in the
first paragraph of their claims file, together with every field they lack and
every claim that lack forbids.
