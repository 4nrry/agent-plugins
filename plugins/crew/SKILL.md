---
name: crew
description: Uses another vendor's agent CLI as an isolated subagent to spend spare quota there — agy (Gemini), opencode (free Zen models), Codex, Grok, Hermes, Copilot, Cursor, Muse, Kimi, or Claude Code when the host is not Claude. Covers a read-only question or multi-turn conversation (ask), a second opinion on a diff (review), and one bounded coding slice under guard hooks and a mechanical gate (delegate), each returning a JSON verdict. Use when the user wants another vendor's model to answer, review or do part of the work, wants to offload a slice, or names one of these CLIs as a worker. Not for the host's own models, which its native subagents serve.
---

# crew

You are the host agent, in whatever tool. A worker is another vendor's CLI run
headless for one turn, or resumed for the next. You write the question or the
task, read the verdict, and check the result. The worker never decides design
or commits.

Commands run from this skill's directory: `python3 scripts/crew.py ...`.

## Before the first run

- Ask the user. A run sends the prompt, and any files the worker reads, to that
  vendor, and spends their quota. Copilot spends AI credits on every run.
- Never route to your own vendor: from Claude Code, use your own subagents for
  Haiku or Sonnet. `ask` refuses a `claude` worker inside Claude Code.
- Workers do not start workers: crew refuses to run inside a crew run
  (`CREW_RUN` is set).

## Pick a backend and a tier

`python3 scripts/crew.py backends` lists each backend's binary, tiers, effort
values, read-only mechanism, and the version it was last tested end to end on.

- Tiers are `cheap`, `mid` and `top`. Each maps to a model and an effort in
  `scripts/backends.py`; `--model` and `--effort` override either one.
- Use free quota first (opencode's free models), then quota the user has
  (agy, Codex, Grok, Hermes), and Copilot last.
- agy has two quota pools. Gemini models are the real budget; its Claude models
  share a small weekly pool. Never use Opus there.
- A backend marked untested had its argv built from `--help` only. Its first
  run may fail on output parsing; say so.

## ask: a question or a conversation

Write the prompt to a file outside the tree, then:

```bash
python3 scripts/crew.py ask <backend> [--tier cheap|mid|top] [--model m] [--effort e] [--cwd repo] --prompt-file q.md
python3 scripts/crew.py ask <backend> --session <session> --prompt-file next.md   # next turn
```

The worker runs read-only in `--cwd`. The verdict's `read_only` says how each
backend enforces this, and a changed work tree fails the run.

Hermes gets no file tools, so put the code in the prompt. Kimi has no verified
read-only headless mode.

The verdict has `ok`, `text`, `session`, `usage`, `failures` and `warnings`;
it never trusts the CLI's exit code alone. Pass `session` back to continue.

## review: a second opinion on a change

```bash
python3 scripts/crew.py review [--backend <backend>] [--diff HEAD~1] [--tier cheap|mid|top] [--model m] --prompt-file q.md
```

Any backend `ask` runs. agy, opencode and Copilot stay read-only through crew's
guard hooks; the others through their own read-only mode, with one more turn in
the same session when the reply lacks the JSON report. Hermes sees only the
question and the diff.

It returns schema'd findings. Check each finding's evidence in the code before
repeating it, and say which ones you confirmed.

## delegate: one slice of coding work

Only agy, opencode and Copilot, whose CLIs run crew's guard hooks. Read
[references/delegate.md](references/delegate.md) for when to delegate, the
task file, the gate, the verdict and the mandatory diff review. Each backend
has its own guard: [agy](references/agy.md), [opencode](references/opencode.md)
and [copilot](references/copilot.md).

## Reporting

Whatever a worker returns is a cheaper or different model's output, not a
decision. Name the backend, model and tier, quote what you verified, and report
`usage` or credits when the user pays for them.

Flags, session resume, extension folders and each CLI's own multi-agent
features: [references/clis.md](references/clis.md).
