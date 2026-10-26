# Batch 2026-10-26-pesquisa-trigger — claims

**Trigger measurements, not run records.** What fires agent-fleet on Portuguese
"pesquisa" prompts and on fan-out words, in Claude Code and in the agents that
run its hooks.

## Description

skill-creator's `run_eval` on the 20 Portuguese prompts of `logs/dev.json` (the
first 20), 3 runs each, `claude -p` on claude-opus-5-5, with the installed
plugin disabled in the scratch folder so only the description under test was
offered: 3 of 30 should-trigger runs invoked the skill (no prompt reached the
0.5 threshold), 0 of 30 near-miss runs did (`logs/description-eval.json`). Same
picture as the English eval of 2026-08-06 (2 of 30). The description is left
as is; the hook carries the trigger.

## Hook

`check_hook.py` pipes each prompt into `hooks/inject.sh` and counts the
agent-fleet header in its output.

| Set | Written | New hook | Hook on main before |
|---|---|---|---|
| `logs/dev.json` (28) | by the author, before the rule | 14/15 fired, 0/13 near-misses | 2/15, 0/13 |
| `logs/blind-1.json` (24) | by a Haiku subagent that never saw the rule; its misses shaped the rule | 12/12, 0/12 | 1/12, 0/12 |
| `logs/blind-2.json` (30) | by a Haiku subagent after the rule was fixed, told to avoid its phrases | 12/15, 0/15 | 0/15, 0/15 |
| `logs/aug-2026-08-06.json` (20) | the 2026-08-06 English eval's queries | 4/10, 0/10 | 1/10, 0/10 |

`logs/blind-2.json` is the honest score. Two of its three misses never say
"pesquisa" ("compara as release notes…", "tem alguma notícia recente…"); the
third ("pesquisa de jurisprudência… pelo menos 5 acórdãos") has no source word
the rule knows. A one-sided rule ("pesquisa" alone) fired on 9 of 13 dev
near-misses: code search, a survey form, a search box, Gmail, ripgrep, a
Postgres index, a typo fix, a pasted article, a TCC section.

## Other agents

The same `inject.sh` runs through `adapters/claude_hooks.py` (Kimi, ZCode,
Muse), the opencode and Hermes bridges, and natively in Grok Build and Cursor.
Through the dispatcher: a market-research prompt and a `/dwf` prompt injected
about 6 KB each; "pesquisa no repo onde calcularFrete() é chamada" injected
nothing. Codex and Antigravity run none of these hooks; there only the
description applies.
