# Cross-cutting benchmark records

`bench/plugins/<name>/` holds work measured on one plugin. This directory is for
records whose finding does not belong to any single plugin — a fact about model
routing, harness behaviour, or measurement method that a second plugin would
reuse rather than re-derive.

- `2026-10-21-skills-and-prompting-research/`: the deep-research run behind
  extension-audit's checklist, with its raw result.
- `2026-10-21-subagents-for-coding-research/`: what Anthropic and recent papers
  say about how many subagents help in coding work.
- `2026-10-21-effort-per-subagent-CLAIMS.md`: how each agent CLI sets reasoning
  effort per worker run and per subagent definition.
- `2026-10-21-agent-cli-inventory-CLAIMS.md`: installed agent CLI versions and
  how each row of crew's `references/clis.md` was confirmed.

`2026-08-07-breadth-tier` is the closest candidate: it
measures which model tier to use for a breadth fan-out, which is a fact about
orchestration rather than about `agent-fleet`. It stays under `agent-fleet`
because that is what it was measured on; move it here the day a second plugin
cites it, and say so in its claims file.
