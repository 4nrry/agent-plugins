# agents-md

Write, trim and audit a repository's AGENTS.md so agents follow it.

```
/plugin install agents-md@4nrry
```

| Component | Path |
|---|---|
| Skill | `skills/agents-md/SKILL.md` — what goes in, what comes out, form, size, cheap audit, upkeep |
| Tool limits | `skills/agents-md/references/tool-limits.md` — what Claude Code, Antigravity and Codex read, and their caps |
| Checker | `skills/agents-md/scripts/check_agents_md.py` — stdlib, `--self-test`, exit 1 when anything is flagged |

The checker reports paths relative to another repo as missing; check before
editing. Queues, ports and env vars are beyond a regex; the skill describes a
cheap per-file verifier for those.

**Evidence:** none recorded. The rules come from an audit of 19 repositories
(files up to 974 lines, one 159 commits behind its code, seven invisible to
Antigravity as `CLAUDE.md`), not from a with/without comparison, so no
improvement claim is made.
