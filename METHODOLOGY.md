# Benchmark methodology

Every rule in the agent-fleet skill traces back to a measured run. This is the
loop that produced them, abstracted from the subject matter so it can be reused
to benchmark any skill, pipeline, or multi-agent setup. The raw evidence
(per-iteration result files, verdict matrices, transcripts) lives in a private
lab workspace; the numbers quoted here are reproduced from it.

## The loop

Draft → run paired arms → verify mechanically → arbitrate verdicts → codify
the lesson → repeat. Nothing enters the skill from intuition alone, and
nothing that was paid for stays only in conversation.

## Rules, each with the run that paid for it

**1. One variable per comparison — and audit the baseline's conditions before
trusting it.** A 14-run "baseline" turned out to vary on four axes at once
(adversarial pass delegated vs inline, breadth tier, skill version, session
mode); filtered to conditions matching the treatment arm, one run remained.
The redo: 5 runs per arm, launched paired, prompts identical except one token
(the model name). Result: mid tier equal to top tier at contesting, 18/20 vs
17/20 — a conclusion the polluted comparison could never have supported.

**2. Consensus ground truth, held loosely.** The answer key came from
majority verdicts across 14 independent runs. Then a paired run showed two
"unanimous" verdicts stopped being unanimous the moment the adversarial pass
was delegated to a subagent: the unanimity was an artifact of the
configuration that produced the key. Part of what a benchmark measures is its
own ruler — say so in the results.

**3. Mechanical verification, self-tested first.** Quotes are string-checked
against fetched pages with no model in the loop — the only check that cannot
be talked into agreeing. The checker itself must prove both ends on known
cases before any of its numbers are believed: a line-wrapped true quote scores
1.0, an invented one below 0.4, a fusion of two non-adjacent sentences is
caught. Seven silent failure modes of this check were paid for and are
documented in the bundled `verify_citations.py`.

**4. Provenance on every claim: measured, official, estimated, or inferred —
stated, not implied.** The skill's cost rule rests on a measured token split
(±5% across ten runs), official per-MTok prices (dated, because one tier was
on a promotional price with an expiry), and estimated phase shares — and the
rule itself ends by telling you to measure the shares instead. Mixed
provenance is fine; undeclared provenance is not.

**5. Two error metrics, because the error points both ways.** Recall alone
rewards a fleet that flags everything. Track over-flagging as its own column.
Measured: breadth fleets under-mark (told to flag uncertainty, they flag
none); every adversarial tier over-marks, on the same two claims, whether mid
or top model. The aggregate hides this; the split shows systematic misses
(one model missed the same claim in 3 of 5 runs) versus noise (another missed
scattered claims once each).

**6. A paid lesson becomes an artifact in the same act.** A skill bullet, a
lint rule, a hook, a version bump — never only conversation. The live run
that found no verbatim sentence on package-table pages became a schema rule
in the next version the same day. If the lesson is not in an artifact, the
next session pays for it again.

**7. Residuals are declared, not forgotten.** What was not tested is written
down as untested, next to what was: a regex proved offline but not live, a
scale regime never exercised, an invocation path inferred from docs rather
than observed. The cheapest future test is the one whose absence is recorded.

**8. Persuasion is measured before it is trusted; when it fails, switch to
mechanism.** Five optimizer rewrites of the skill's trigger description, each
informed by the previous failures, moved held-out recall not at all (0.00 to
0.33 on ideal queries; the best description remained the original). A
twenty-line prompt hook made triggering deterministic with zero false fires
on the same eval set. Wording is a hypothesis to test, not a lever to lean on.

**9. Each new form retires the old one in the same act.** Hook in settings →
skills-dir plugin → marketplace plugin: every migration deleted its
predecessor at the moment of the switch, verified by sweep. Two live copies
of an injector means double injection; the absence of leftovers is part of
the change, not cleanup for later.

**10. Document while working, not after.** The lab notebook — a per-iteration
result file recording not just the score but why the design is what it is —
is what survives context-window compaction. Sessions end and windows shrink;
the notebook plus raw transcripts reconstruct everything except the dead ends
that were never written, and those are the only real loss.

## Benchmark mechanics that recur

- Paired arms are launched in the same turn, so they hit the same conditions.
- 3 runs per query for trigger rates; 5 per arm for verdict comparisons —
  enough to separate systematic error from noise, cheap enough to repeat.
- Held-out splits (60/40) for anything an optimizer touches, selected by test
  score, never train.
- Closed output schemas with the verdict boundary cases defined — left open,
  each model settles right-conclusion-wrong-mechanism by disposition, and the
  aggregate moves with the model instead of the work.
- Structural containment over prompt instructions: collectors get a toolset
  with no write tool, measured after prompt-level bans failed twice.
