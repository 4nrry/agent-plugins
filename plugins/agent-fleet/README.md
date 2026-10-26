# agent-fleet

Rules for multi-agent work: model routing per phase, fan-out sizing, closed
output schemas, and verifying what agents return.

```
/plugin install agent-fleet@4nrry
```

The skill lives in `skills/agent-fleet/` and the plugin ships an Agent Plugins
`plugin.json` at its root, so Copilot, Codex and Cursor can install it; other
harnesses get the skill folder through `link_skills.py`. The hooks and the
workflow are Claude Code only. Paths below are relative to the skill folder,
except `hooks/` and `workflows/` at the plugin root.

| Component | Path | Does |
|---|---|---|
| Skill | `SKILL.md` | The rules, in tiers rather than model names |
| Harness map | `references/harnesses.md` | Tiers, model setting and read-only children per harness |
| CLI workers | `references/cli-workers.md`, `scripts/fleet_worker.py` | Search and extract on another CLI through crew's `ask --web --schema`, read-only |
| Verifier | `scripts/verify_citations.py` | Fetches each cited URL and string-checks the quote |
| Workflow | `workflows/deep-research.js` | Claude Code's built-in deep research with per-phase `model:` overrides |
| Injection hook | `hooks/inject.sh` | `UserPromptSubmit`: loads the skill when the prompt names a fan-out (`ultracode`, deep research, dynamic workflow, `/dwf`, `/fleet`) or asks for "pesquisa" from many sources; says to search X only when the question is about posts or the user asks |
| Routing hook | `hooks/check-routing.sh` | `PreToolUse` on `Workflow`: denies an unrouted script once, and the bare built-in name always |

## Why hooks

The skill's description fired on 2 of 30 should-trigger runs, and no rewrite
helped, so a substring hook loads it instead. The routing rule was loaded
during a ~97-agent run that still inherited the top model, so a hook checks
for it at dispatch.

## Evidence

Records and claims live in [`bench/plugins/agent-fleet/`](../../bench/plugins/agent-fleet/):
the trigger eval, the hook-grep batch, the breadth-tier batch, and the
fleet-worker smoke notes. The rules in the skill come from earlier paired runs
that predate the bench protocol; read those as design notes.

`workflows/deep-research.js` is the 2.1.306 built-in plus `model:` overrides;
its header says how to rebase it when the built-in changes.
