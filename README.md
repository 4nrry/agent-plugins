# 4nrry's Claude Code plugins

Personal plugin marketplace for [Claude Code](https://code.claude.com/docs/en/plugins).

## Install

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
