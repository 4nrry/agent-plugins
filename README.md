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
invokes deep-research or ultracode. The hook exists because measurement showed
the description alone never triggers the skill (recall 0.00–0.33 across five
optimizer rewrites, on an eval set where the string match scores zero false
positives) — so triggering is mechanical, not persuasive. Every rule in the
skill body comes from paired A/B runs; the design notes live in the skill
itself.

## Methodology

How these rules were measured — the benchmark loop, one rule per paid lesson —
is documented in [METHODOLOGY.md](METHODOLOGY.md).
