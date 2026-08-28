# Batch 2026-08-20-hook-grep — claims

**Question:** the hook's own header says it injects the skill when the prompt
*invokes* deep-research or ultracode. Does its string match separate
invocation from mention?

This is a **different benchmark from `2026-08-06-trigger-eval`**, on a
different mechanism. That batch measured whether the skill *description* fires
the skill passively, judged by a model. This one measures the
`UserPromptSubmit` hook that replaced it — a `grep -qiE` in
`plugins/agent-fleet/hooks/inject.sh`, no model anywhere in the loop. The two
eval sets are not comparable and neither one's numbers transfer to the other
mechanism. In particular, **the "0 false fires in 150 negative runs" figure
belongs to the description and says nothing about the grep.**

**Origin:** not a planned experiment. On 2026-08-20 the hook fired during a
conversation about renaming this repository, because the user's message
mentioned "deep research" and "ultracode" while describing past benchmarking
work. Nothing was being orchestrated. That prompt is **eval item 5**,
transcribed byte-for-byte including its typos; the other eleven items were
written afterwards to place it in a class.

**Variable:** none — this is a pilot establishing current behaviour, not a
comparison. **Arm:** pilot. **n:** 1 per item, and 1 is sufficient here: the
apparatus is a shell grep, so the measurement is deterministic. Confirmed by
running the scorer twice and hashing its JSON output — identical
(`8f1329a897b3…`). The protocol's floor of 3 repetitions per query exists for
stochastic trigger rates; a grep has no rate to average.
**Eval:** `bench/plugins/agent-fleet/evals/hook-grep-2026-08-20.json`, sha256 `cbbf963bcc4e…6bb4`
— 12 items, 4 invocation / 8 mention, mostly Portuguese.
**Apparatus under test:** `hooks/inject.sh`, sha256 `ee999cd472f3…d42b`
(historical — comment-only edits since; see *Deviations*).
**Verifier:** `bench/plugins/agent-fleet/scripts/score_hook_grep.py`, self-test passed (it asserts
a known fire *and* a known silence — a matcher that fires on everything passes
either half alone).

## Results (all from the verifier, `source: "script"`)

| class | items | fired | reading |
|---|---|---|---|
| invocation | 4 | **4/4** | recall 1.00 |
| mention | 8 | **8/8** | false-fire rate 1.00 |

## Claims

1. **The grep does not distinguish invocation from mention: it fired on 8 of 8
   mention items.** This is not a tuning gap, it is the shape of the matcher —
   it tests for the presence of a substring and has no access to whether the
   user is asking for a fan-out or talking about one. Item 7 is the sharpest
   case: a prompt *asking whether the pattern is too broad* trips the pattern.
2. **Recall on genuine invocation is perfect: 4 of 4**, across the slash form,
   the natural-language form, the space variant and the hyphen variant. The
   hook does the job it was added for. Claim 1 is about a cost it also
   carries, not a failure to trigger.
3. **The observed case was real, not constructed.** Item 5 fired in a live
   session that orchestrated nothing. Until 2026-08-20 this class had no
   coverage: the 2026-08-06 negative set probes *adjacent vocabulary*
   ("crio um subagente customizado", "spawna os workers") and contains no item
   in which the literal trigger strings appear. Perfect precision was measured
   on a set that excluded the only class that can fail this matcher.
4. **The hook covers explicit naming only, and that is the whole of it.**
   Run read-only against the frozen 2026-08-06 eval (sha256 `aaf1f84d…6ff7`,
   unmodified), the grep fires on **1 of its 10 should-trigger queries** and
   **0 of its 10 should-not**. Those ten positives were written to test whether
   the skill surfaces on queries where it is relevant *without the user naming
   it* — exactly the class a substring match cannot reach. So the two batches
   together read: the description almost never fires on implicit relevance
   (2/30 runs), and the hook that replaced it does not either (1/10 queries) —
   it converts *explicit* invocation into reliable injection, and leaves
   implicit relevance uncovered. Neither record shows that gap closed; the
   hook moved the mechanism, not the coverage.

5. **The cost of a false fire is 10,056 bytes of injected context** — the
   hook's preamble plus the whole of `SKILL.md`, measured with `wc -c` on one
   firing. In tokens that is roughly 2.5k, **estimated by dividing by 4
   bytes/token and not tokenized**, so treat it as an order of magnitude.

## What this does not establish

- **Not that the hook should be narrowed.** Injecting orchestration rules into
  a conversation *about* orchestration is not obviously wrong — it may be
  useful — and the cost is context tokens, not a wrong answer. This batch
  measures the rate and the payload size; whether that trade is worth changing
  is a judgement no record here settles. Any narrowing is also a precision/
  recall trade against claim 2, and would need its own paired arms.
- **Not a general false-fire rate.** 8 of 8 is 8 items chosen *because* they
  contain the trigger strings. The population rate depends on how often the
  user writes about this work versus asks for it — unmeasured, and for a
  repository whose subject is fleet orchestration, plausibly not rare.
- **No cost claim about a pipeline.** No agents ran; `agents[]` is empty and
  every token total in the record is zero.

## Deviations and threats

- **The eval was frozen after the observation, not before it.** Protocol step 2
  wants the set frozen before the first run. Item 5 could not be: it was
  observed in the wild, and the other eleven items exist to give it a class.
  The set was frozen and hashed before the verifier was first run against it,
  which is the part that still holds.
- **The class labels are the researcher's judgement.** "Invocation" versus
  "mention" is drawn by hand. Item 8 ("quanto custou o ultimo deep research")
  and item 12 (explain the difference) are the ones a reasonable person could
  relabel; moving both would change the mention column to 6/6 and change no
  conclusion.
- **One matcher, one machine, one hook version.** The result was measured
  against `hooks/inject.sh` at sha256 `ee999cd472f3…d42b` (historical — the
  file has changed since, see below). Editing the *pattern* invalidates this
  batch; the file has so far only had comment edits, and no HEAD hash is
  quoted here on purpose. Two of them rotted within a day of being written —
  once when claim 1 was acted on and the header stopped saying the hook fires
  on "invocation", once when `bench/` was namespaced by plugin and the paths
  in that same comment moved. What guards the result is not a quoted hash but
  `bench/validate.py`, which re-runs this batch's scorer on every `just check`:
  if the matcher's behaviour ever drifts from 4/4 and 8/8, the build fails.
- **The verifier and the eval were written in the same session by the same
  author as the observation.** No independent replication.
