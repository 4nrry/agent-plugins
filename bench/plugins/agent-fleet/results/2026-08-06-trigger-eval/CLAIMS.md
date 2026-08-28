# Batch 2026-08-06-trigger-eval — claims

**Question:** does agent-fleet's skill *description* fire the skill passively —
without the user naming it — on the queries it was written for?

This is the measurement the plugin's `UserPromptSubmit` hook exists because of.
It is an **imported record**: it was collected on 2026-08-06, before
`bench/PROTOCOL.md` was written, by the description optimizer bundled with
Anthropic's `skill-creator` skill (`run_loop`). It does **not** conform to
`schema/run.schema.json` — see *Deviations* — and it is published as the raw
harness output, byte for byte, rather than retrofitted into a shape it was
never measured in.

**Variable:** the description text. **Arms:** five descriptions — iteration 1
is the **original** (the one the plugin ships), iterations 2–5 are the
optimizer's four rewrites, each written after seeing the previous failures.
**n:** 3 runs per query per description → 300 runs total (150 on
should-trigger queries, 150 on should-not). **Eval:**
`bench/plugins/agent-fleet/evals/trigger-eval-2026-08-06.json`, sha256
`aaf1f84d…6ff7` — 20 queries, 10 should-trigger / 10 should-not, mostly in
Portuguese because that is how this user writes; split 12 train / 8 test
(holdout 0.4) by the harness. **Judge model:** `claude-fable-5`, the session
model at the time. **Raw output:** `results.json`, sha256 `9c37834f…a064`;
`logs/improve_iter_{1..4}.json` are the optimizer's four rewrite prompts and
responses — four log files, one per rewrite, which is the structural
corroboration that there were four rewrites and not five.

## Per-description results (all from `results.json`)

| description | should-trigger queries that fired at all | positive runs that fired | best single query | false fires | train | test |
|---|---|---|---|---|---|---|
| **1 — original (shipped)** | 2/10 | **2/30** | 1 of 3 | 0/30 | 6/12 | 4/8 |
| 2 — rewrite | 4/10 | 4/30 | 1 of 3 | 0/30 | 6/12 | 4/8 |
| 3 — rewrite | 4/10 | 5/30 | 2 of 3 | 0/30 | 7/12 | 4/8 |
| 4 — rewrite | 7/10 | 9/30 | **3 of 3** | 0/30 | 7/12 | 4/8 |
| 5 — rewrite | 5/10 | 5/30 | 1 of 3 | 0/30 | 6/12 | 4/8 |

The harness scores a query as passed when it fires in a **majority of its 3
runs** — inferred from the data, not documented by the harness: across all 300
runs, no positive query passes with fewer than 2 triggers and none fails with
2 or more. By that bar, **2 of 50 positive query-slots passed in the entire
experiment** (one under description 3, one under description 4).

## Claims

1. **The shipped description almost never fires passively: 2 of 30 positive
   runs.** Per-query recall spans 0.00–0.33 — no should-trigger query fired in
   more than 1 of its 3 runs. The failures include the cases the skill was
   written for: an explicit `/deep-research …` prompt (0 of 3), the 50-states
   legal survey that had previously ballooned into 200 agents (0 of 3), "spin
   up a bunch of subagents … i want verbatim quotes" (0 of 3).
2. **Zero false fires, all five descriptions: 0 of 150 negative runs.** The
   negatives deliberately carry the adjacent vocabulary — "crio um subagente
   customizado", "escreve um agente … com a API da anthropic", "multiprocessing
   … spawna os workers", "listar minhas rotinas agendadas" — so this is
   precision under pressure, not an easy set. It is also why the hook's string
   match was kept narrow.
3. **No rewrite improved the held-out score: 4/8 for all five descriptions.**
   That is the metric the loop selected on, and why the original was kept.
4. **Raw firing did move, and the headline range does not cover it.**
   Description 4 fired on 9 of 30 positive runs against the original's 2, and
   reached 3 of 3 on one query. The precise statement is therefore *the shipped
   description's per-query recall is 0.00–0.33, and no rewrite improved the
   held-out score* — not *no rewrite ever fired more often*. Anywhere this
   repository says "0.00–0.33", it is describing description 1.
5. **The conclusion the plugin acts on:** passive triggering is not a wording
   problem, so it was not solved with wording. Triggering became mechanical —
   a `UserPromptSubmit` hook that greps `ultracode|deep[- ]research` and
   injects the skill body. Claim 2 is what makes a narrow grep the right
   shape: the description's precision was already perfect, and the rewrites
   that chased recall never bought any.

## Deviations and threats

- **Imported record, no schema conformance.** No per-agent token splits, no
  wall durations, no `batch_id`, no `orchestrator_prompt_sha256` — the harness
  did not emit them. Consequently **no cost claim is derivable from this
  batch**, and none is made. The two hashes above are the provenance that a
  reader can check against their own copy.
- **The eval file is the optimizer's shape** (`query` / `should_trigger`), not
  `schema/eval.example.json`'s (`input` / `expected` / `assertions`). The assertion
  is implicit in the harness: did the skill get invoked, yes or no.
- **The judge is the harness's own trigger detection**, run under one model
  (`claude-fable-5`) on one machine, and was not independently re-verified. A
  different session model may weigh a description differently; that is
  untested.
- **The pass threshold is inferred** from the pass/trigger pairs, as described
  above, not stated by the harness in the record.
- **The train/test split affects only the optimizer's selection.** Every recall
  number here pools both halves, because a query's trigger rate does not depend
  on which half it landed in.
- **The negative set is 10 queries.** Perfect precision on 150 runs of 10
  queries is not perfect precision in general.
