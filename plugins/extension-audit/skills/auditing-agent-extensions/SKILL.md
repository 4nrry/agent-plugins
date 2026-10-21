---
name: auditing-agent-extensions
description: Audits agent skills, plugins and hooks against Anthropic's authoring best practices and current prompting research, combining a mechanical linter with a sourced checklist. Use when reviewing or cleaning up a SKILL.md, a Claude Code plugin, a hooks.json or a marketplace repo, before publishing one, or when asked whether an extension follows best practices.
---

# Auditing agent extensions

## Workflow

Copy this checklist and track it:

```
Audit progress:
- [ ] 1. Run the linter
- [ ] 2. Run the platform validator
- [ ] 3. Walk the judgment items in the checklist
- [ ] 4. Report findings
- [ ] 5. Decide on behavioral evals
```

**1. Linter.** From this skill's directory:

```bash
python3 scripts/lint_extensions.py <repo-or-plugin-dir>          # text report
python3 scripts/lint_extensions.py <dir> --json                   # machine-readable
```

Exit 1 means at least one `error`. Fix errors first; `warn` items need a
decision, not always a change. Run `--self-test` once if the output looks off.

**2. Validator.** For Claude Code plugins, `claude plugin validate --strict <plugin-dir>`.
It checks the manifest and paths, not behavior.

**3. Checklist.** Read [references/checklist.md](references/checklist.md) and
check every item not marked `[lint]` against the files. Read each SKILL.md in
full; do not sample.

**4. Report.** One line per finding: `path:line — rule — fix`. Group by
severity. Say which items you could not check and why.

**5. Evals.** A clean audit proves form, not effect. When the extension's
value is in doubt, measure it against a no-extension baseline: `claude plugin
eval` for a plugin, the skill-creator plugin for a single skill. Use several
prompt variants per case; one prompt is not a measurement.

## Rules for the audit itself

- Cite the file and line for every finding.
- Prefer the platform's current docs over memory; the checklist links them.
  If a linked page contradicts the checklist, the page wins — note it.
- Do not rewrite an extension during the audit unless asked. Report first.
