# Batch 2026-11-10-anthropic-tools — claims

**Notes, not run records.** Why extension-audit 0.2.0 adds what it adds. On
2026-11-10, with Claude Code 2.1.322, extension-audit 0.1.1 was compared with
the checks Anthropic ships: `claude plugin validate` (with and without
`--profile directory`), the plugin-dev plugin 0.1.1 (its plugin-validator and
skill-reviewer agents), and the skill-creator skill (`quick_validate.py` and
`run_eval.py`). Targets: media-agent 0.18.0 and its `page-check` and
`cutout-animation` skills, the other seven plugins, and planted defects.

**On the real plugins.** extension-audit 0.1.1, `just check` and
`quick_validate.py` found nothing. `claude plugin validate --strict` passed
media-agent. With `--profile directory` it failed all eight plugins on one
code, ICON_MISSING, and nothing else.

**Planted defects.** Skills built to carry one defect each, wrapped in a
throwaway plugin where the CLI needs one.

| Defect | extension-audit 0.1.1 | quick_validate.py | CLI |
|---|---|---|---|
| unquoted `: ` in the description | error | error | missed |
| a quote never closed | missed | error | error |
| name not matching the directory | error | error | missed |
| a frontmatter key no host reads (`foo`) | missed | error | missed |
| description of 1,499 chars | error | error | missed |
| body of 602 lines | error | missed | missed |
| broken relative link | error | missed | missed |
| marketing word, first person | warn | missed | missed |
| `SKILL.md` inside another skill | missed | error | missed |
| no README, LICENSE or icon | missed | n/a | `--profile directory` only |

`quick_validate.py` stops at the first error; the linter lists every finding
with a line.

**After the change.** extension-audit 0.2.0 reports each row the 0.1.1 column
missed: the unclosed quote and the unknown key as errors, the nested
`SKILL.md` as a warning, README, license and icon with `--directory`. With
`--directory` over `plugins/` it reports the same eight missing icons as the
CLI and nothing else.

**The model reviewers.** plugin-dev's skill-reviewer found real behavior gaps
in both skills that no mechanical check reaches, and several false ones from
out-of-date rules: a description over 500 chars called too long (the spec
allows 1,024), a body under 1,000 words called too short, and a required
"This skill should be used when" opening. Its plugin-validator did not
mention the icon. Nothing from plugin-dev was adopted.

**Trigger rate.** skill-creator's `run_eval.py` ran on this machine through
`claude -p` with the Claude Code login: 4 queries for `cutout-animation`, one
run each, 3 of 4 as expected, about 10 s. That shows it runs; one run per
query is not a rate. Started from a directory with no `.claude/` of its own,
it would have written its temporary command into the home directory's
`.claude/commands/`.

**Not measured.** The claude.ai portal's own checks beyond what the CLI
documents; OpenAI's directory; whether any plugin here gains from a
`claude plugin eval` suite (none has one).
