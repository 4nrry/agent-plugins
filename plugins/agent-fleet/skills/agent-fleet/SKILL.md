---
name: agent-fleet
description: Rules for multi-agent work — routing each phase to the right model, sizing a fan-out, constraining output schemas so budget is not spent on text you discard, and verifying what agents return. Read this before any deep-research run, whether invoked by name or triggered implicitly by a question that needs many sources, and before launching subagents, a dynamic workflow, an agent team, or any parallel run. Read it again when the results come back and you must decide what to trust. Consult it even when the user never says "deep research", "fleet", "fan-out" or "subagent" — any time work is about to be split across several agents, or a batch of agent findings needs checking.
---

# Agent Fleet

Agents are cheap to launch and expensive to trust. These rules cover what to
send them and what to believe when they come back. Tiers, not models: cheap,
mid, and you, the orchestrator — [references/harnesses.md](references/harnesses.md)
maps them per harness.

## Before dispatch

- Read any predefined workflow (a deep-research command, a saved script, a set
  of agent definitions) and find where each agent's model is set. Unset means
  every agent inherits your model: a top-tier session pays top tier per agent.
  A ~97-agent run did exactly that with these rules loaded. If caught late,
  stop and resume with overrides where the harness can resume.
- A scripted fan-out returns only its final answer, so get the schema right
  before the run.

## Model choice

- Route by phase. Long tool loops (search, fetch, copy exactly) go to the cheap
  tier; the adversarial pass goes to the mid tier, which matched the top model
  at contesting in paired runs. Widening the fan-out buys coverage, not
  correctness.
- Route effort with the model: search and fetch loops run the cheap tier at
  low effort. A subagent or workflow `agent()` with no effort set inherits the
  session's, so set both where you set the model.
- A small model detects well and writes unsafely: it fuses non-adjacent
  sentences and drops qualifiers. Cheap is safe only with a closed schema and
  string-checked quotes.
- Its failures are diligence — prose in an identifier field, a real quote on
  the wrong URL. Tighten the schema; a bare `string` invites a status sentence.
- Price the mix, not the volume: a routed run spends about the same tokens on
  a cheaper meter. Look up current prices; when cost matters, have each agent
  report its tokens.

## Fan-out

Sizes and coding rules below come from the subagents-for-coding research
record in `bench/shared/`.

- For coding, default to one agent. On SWE-bench Verified every multi-agent
  setup scored below a single agent; task structure, not agent count, decides.
- Fan out only independent, mostly read-only subtasks: search, review,
  separate modules. Never several agents editing coupled code.
- Keep it small, 3–5 agents. That size, and over 10 for complex work, comes
  from research tasks; no source gives one for coding.
- Count the cost first: vendors report 3–10x a single agent's tokens.
- Fan out for breadth, never for prose. Agents find; you write.
- Pipeline independent items. Add a barrier only when the next step needs the
  whole set (dedup, total, early exit): it costs the slowest item every time.
- Ask only for fields you will use — status, evidence, URL, verbatim quote —
  and read every one. For verdict enums, define the boundary cases (right
  conclusion, wrong mechanism); left open, models split by disposition.
- On structured pages (tables, version lists) the verbatim unit is the cell,
  not a sentence.
- Triage instead of waves: one agent per item, a mechanical filter over the
  results, depth only on what the filter flagged.
- Several small runs beat one large one; try one item solo first.
- Forbid writes with a toolset that cannot write, not with a sentence. A
  collector told not to overwrite a file did it anyway in two runs.
- Bound installs in the prompt: simulate, or use a throwaway container.
- The cheap tier can be another CLI: `scripts/fleet_worker.py` runs search and
  extract on grok, agy, hermes, codex, claude or opencode, read-only, through
  the crew plugin's `ask`. See
  [references/cli-workers.md](references/cli-workers.md). Ask the user before
  the first run: it spends their quota or sends the question to that provider.

## Verifying what comes back

- Every claim carries a fetched URL and a verbatim quote. Check by fetching and
  string-matching, no model in the loop: run `scripts/verify_citations.py`
  (`--self-test` first). It is the only check that catches a real quote on the
  wrong source.
- Read the match ratio, not pass/fail. About half or less means written from
  memory. Above a sentence the ratio means presence, not support: check where a
  short quote landed, unless it is a distinctive identifier.
- An unreachable page is neither pass nor fail. Open it in the harness's
  built-in browser if it has one (it renders scripts and carries the user's
  session), or try an archive mirror; keep a per-project list of hosts that
  refuse scripts.
- Verify verdicts in both directions: the breadth tier under-marks uncertainty,
  an adversarial pass over-marks caveats. A contester's caveat is a claim to
  check, not a correction to accept.
- Rewrite verifier text to your own register before using it.
