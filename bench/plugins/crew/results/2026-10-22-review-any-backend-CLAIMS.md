# Batch 2026-10-22-review-any-backend — claims

**Smoke notes, not run records.** n=1 per backend, tier `cheap`. A throwaway
repo whose last commit turns `add(a, b)` (docstring "Return the sum of a and
b.") into `return a - b`. Each backend got `crew.py review "Is this change
correct?" --diff HEAD~1`. Verdicts stayed in the session scratchpad and were
not committed. They show the review path works end to end on backends without
crew's guard hooks. They do not measure review quality.

| Backend | Verdict | Findings | Turns | Note |
|---|---|---|---|---|
| codex | request_changes | 1 high, `calc.py:3` | 1 | |
| grok | request_changes | 1 high, `calc.py:3` | 1 | |
| hermes | request_changes | 1 high, `calc.py:3` | 1 | saw only the question and the diff (`-t web`) |
| claude | request_changes | 1 high, `calc.py:3` | 1 | haiku, $0.024 |

Every report matched the default schema on the first turn, so the
same-session retry for a missing report ran only in `--self-test`, against a
fake CLI. The work tree was unchanged after every run.
