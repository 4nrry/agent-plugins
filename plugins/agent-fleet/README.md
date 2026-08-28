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
