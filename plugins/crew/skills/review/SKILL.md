---
name: review
description: Gets a read-only second opinion on a diff or files from a cheaper model — Gemini through agy in plan mode with a schema'd report, a free model through opencode, or GitHub Copilot CLI with no shell and no writes. Use when the user asks for a second opinion, a cheap review, or a review by agy, opencode or Copilot.
argument-hint: [--backend agy|opencode|copilot] [--diff HEAD~1] [--model slug] <what to review>
---

# Read-only review by a worker

Write the question to a file outside the tree (free text breaks the command
line on quotes, parentheses or `;`), then run, from the `delegate` skill's
directory:

```bash
python3 scripts/crew.py review [--backend agy|opencode|copilot] [--diff HEAD~1] [--model slug] --prompt-file /path/question.md
```

Without `--diff` the reviewer only reads files; pass a range when the
question is about a change. Ask the user before the first `delegate` or
`review` of a session: the code goes to the backend's provider and spends
quota or credits. How each backend stays read-only is in its skill.

When reporting: it is a cheaper model's second opinion, not a decision. Check
each finding's `evidence` in the code before repeating it — line numbers can
be wrong — and say which you confirmed.
