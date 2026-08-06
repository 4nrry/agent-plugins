---
name: agent-fleet
description: Rules for multi-agent work — routing each phase to the right model, sizing a fan-out, constraining output schemas so budget is not spent on text you discard, and verifying what agents return. Read this before any deep-research run, whether invoked by name or triggered implicitly by a question that needs many sources, and before launching subagents, a dynamic workflow, an agent team, or any parallel run. Read it again when the results come back and you must decide what to trust. Consult it even when the user never says "deep research", "fleet", "fan-out" or "subagent" — any time work is about to be split across several agents, or a batch of agent findings needs checking.
---

# Agent Fleet

Agents are cheap to launch and expensive to trust. These rules cover both
halves: what to send them, and what to believe when they come back.

`/deep-research` is the usual consumer, and its four stages map onto the
sections below — the fan-out is sized here, the model for each stage is chosen
here, and "adversarially verify claims" is the section on what comes back. The
synthesis stage is the one the rules hand to you rather than to an agent.

Under `ultracode` the fan-out stops being a decision and becomes the session
default, because Claude orchestrates dynamic workflows for substantive tasks on
its own. A dynamic workflow also changes what you get to see: the script holds
the loop and the intermediate results, and only the final answer reaches the
context — so the schema has to be right *before* the run, not after.

## Model choice

- Route by phase, not by task. Long tool loops — fetch, retry, copy exactly —
  hold the volume and run fine on the cheapest tier. Adversarial passes need
  depth, and that is where depth pays: a corrected verdict comes from the pass
  that contests it, almost never from the breadth that found it. So widening
  the fan-out buys coverage, not correctness, and the budget belongs to the
  pass that argues back. The mid tier delivers that depth: paired runs put it
  even with the top model at contesting, so no stage of the pipeline needs an
  expensive subagent — the top model's remaining edge is orchestrating.
- A small model is a good detector and an unsafe writer for source-grounded
  work: recall holds up, quote fidelity does not — it fuses two non-adjacent
  sentences, drops the one qualifying word, and the result still reads right.
  Cheap is safe here only because the schema is closed and the quotes are
  string-checked; without both, this stops being true.
- Its failures are diligence, not reasoning — prose in identifier fields, a
  real quote attached to the wrong source URL, which passes a reading review.
  So tighten the schema rather than avoid the model; a bare `string` invites a
  status sentence, and it validates.
- Price the mix, not the volume. A routed pipeline spends roughly the same
  tokens as an all-top-tier one; the saving is that most of them run on a
  cheaper meter. Check whether the tiers currently scale uniformly across
  input and output — when they do, the cost ratio between tiers is all you
  need, and phases can be costed by token share alone. Breadth holds the
  volume, so the larger the fan-out, the closer total cost converges to the
  breadth tier's rate: the orchestrator's expensive share shrinks as the fleet
  grows. Look up current per-MTok prices instead of carrying them from memory,
  and when cost is the target, have each agent report its token total back so
  the mix is measured rather than estimated.

## Fan-out

- Fan out for breadth, never for prose. Agents find; you write — agent-written
  drafts get rewritten by hand anyway. Check what survived the last fan-out
  before designing the next.
- Size by the shape of the work, not by ambition. Independent items belong in a
  pipeline, each finishing as it can. A barrier that waits for the whole set
  earns its cost only when the next step genuinely needs all of it — a dedup, a
  total, an early exit — because a barrier is priced at its slowest item every
  time.
- Constrain the output schema to what will be used: status, evidence line,
  citation, URL, verbatim quote. A free-text proposal field spends the budget
  on the part you throw away — and read every field you did ask for, since one
  you never open is budget spent on nothing. When a field enumerates verdicts,
  define the boundary cases too — where does right-conclusion-wrong-mechanism
  fall? Left open, each model settles it by disposition, one reading it as
  false and another as true-with-a-caveat, both defensibly — the largest
  source of verdict variance in paired runs, and it moves your aggregate with
  the model choice.
- Prefer several small runs to one large one; resume by run id rather than
  relaunching.
- Try small and solo first — one fetch, one quote check, a ten-line throwaway
  script.
- Triage rather than staging waves. One agent per item for breadth, then a
  mechanical filter over everything they returned, then depth only on what the
  filter flagged. A wave per stage — fifty to find, fifty to summarise, fifty
  to audit — pays a model three times per item, and two of those three produce
  either prose you were going to rewrite or a check a script does better and
  cheaper. The filter is what shrinks the fleet: it decides which handful is
  worth an expensive second look.
- Bound what agents may install, in the prompt. Simulating an install answers
  availability, a throwaway container answers behaviour, and the host gets only
  what the user approved; auditing the machine afterwards is the expensive
  fallback. Container results transfer for behaviour, not for timing or
  anything needing a desktop.
- Forbid writes structurally when the task is detection, not in prose. A
  detector that can also delete will eventually delete something it misjudged
  — and telling it not to is weaker than it looks. In two measured runs a
  collector overwrote a shared file despite an explicit ban in its own prompt,
  and the behaviour stopped only when the agent type changed to one with no
  write tool in its box. Hand out a toolset that cannot write; the sentence in
  the prompt is a courtesy to a fleet that already can't, not a control.

## Verifying what comes back

- Every claim carries a URL the agent fetched and a verbatim quote. Verify by
  fetching and string-searching, no model in the loop — the only check that
  cannot be talked into agreeing, and the only one that catches a real quote on
  the wrong source. Use `scripts/verify_citations.py` instead of writing your
  own: run `--self-test` first, which proves both ends in two seconds. Its
  header lists seven ways this check silently fails, each of which turns a true
  quote into an apparent fabrication — the expensive outcome, because you then
  go and correct something that was already right.
- Report near-misses as a ratio, not pass/fail. Markup breaks sentences across
  tags; roughly half or less means the agent wrote from memory. The ratio only
  carries information above a sentence or so, and a high one proves presence,
  not anchoring — three tokens will match somewhere on almost any page,
  including the paragraph that does not support the verdict. On a short quote,
  check where it landed rather than whether it landed.
- An unreachable page is its own answer — neither pass nor failure. Some hosts
  refuse scripted GETs, some render client-side. Keep a per-project list rather
  than rediscovering it each run; archive mirrors and plain-HTML alternatives
  usually work.
- Treat a verifier's corrected text as research, not copy. Rewrite it to the
  surrounding register.
- Verify the agents' verdicts, not just their findings — and expect the error
  to point both ways. The breadth fleet under-marks: told to flag uncertainty,
  it flags none, and hands back dry verdicts. A delegated adversarial pass
  over-marks: it wants a caveat on claims nobody disputes, in every tier —
  measured on the same two claims with both a mid and a top model contesting.
  You arbitrate both directions. A contester's caveat is a claim to verify
  against the source, not a correction to accept.
