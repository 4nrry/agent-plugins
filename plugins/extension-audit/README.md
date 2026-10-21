# extension-audit

Audits agent skills, plugins and hooks against Anthropic's authoring guidance
and current prompting research.

```
/plugin install extension-audit@4nrry
```

| Component | Path |
|---|---|
| Skill | `skills/auditing-agent-extensions/SKILL.md` — the audit workflow |
| Checklist | `skills/auditing-agent-extensions/references/checklist.md` — every item with its source; `[lint]` marks the mechanical ones |
| Linter | `skills/auditing-agent-extensions/scripts/lint_extensions.py` — stdlib, `--json`, `--self-test`, `--plugin-validate` |

The skill folder is self-contained, so it also works copied into
`.agents/skills/` for other harnesses. In this repo, `just check` runs the
linter over `plugins/`: errors fail the build, warnings are listed.

A clean lint run proves form, not effect; measure effect with
`claude plugin eval` against a no-plugin baseline.
