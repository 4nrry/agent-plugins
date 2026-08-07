# Batch 2026-08-07-breadth-tier — claims

**Question:** does the breadth-fleet model tier (haiku vs sonnet) change
citation fidelity and key-fact recall under closed schema and read-only
containment?
**Variable:** breadth agent model. **Arms:** `haiku`
(claude-haiku-4-5-20251001), `sonnet` (claude-sonnet-5) — resolved IDs from
transcripts. **n:** 5 runs per arm, launched paired in the same turn, rounds
1–5. **Eval:** `bench/evals/plasma67-citations.json`, sha256 `058df2a5…6948`,
frozen and committed before round 1. **Arm script:**
`bench/scripts/breadth-tier-arm.js`, sha256 `4acdd374…de9c` — byte-identical
across arms, recorded as `orchestrator_prompt_sha256` in every run. **Scorer:**
`bench/scripts/score_plasma67.py` over the plugin's `verify_citations.py`
(self-test passed before every scored run).

## Per-run results (records in this directory, `…-<arm>-r<n>.json`)

| run | verbatim ≥0.8 | rate | schema | key facts | wrong source | output tok | wall s |
|---|---|---|---|---|---|---|---|
| haiku-r1 | 11/14 | 78.6% | 4/5 | 3/5 | 0 | 17,877 | 162 |
| haiku-r2 | 14/17 | 82.4% | 5/5 | 4/5 | 0 | 14,807 | 98 |
| haiku-r3 | 15/19 | 78.9% | 5/5 | 5/5 | 0 | 11,758 | 101 |
| haiku-r4 | 9/16 | 56.2% | 5/5 | 4/5 | 0 | 11,958 | 90 |
| haiku-r5 | 12/18 | 66.7% | 5/5 | 5/5 | 0 | 14,590 | 183 |
| sonnet-r1 | 15/21 | 71.4% | 5/5 | 4/5 | 0 | 17,679 | 140 |
| sonnet-r2 | 15/21 | 71.4% | 5/5 | 4/5 | 0 | 21,964 | 131 |
| sonnet-r3 | 13/19 | 68.4% | 5/5 | 3/5 | 0 | 16,989 | 201 |
| sonnet-r4 | 20/22 | 90.9% | 5/5 | 4/5 | 0 | 15,339 | 70 |
| sonnet-r5 | 13/17 | 76.5% | 5/5 | 4/5 | 0 | 20,536 | 124 |

## Aggregates

| | haiku | sonnet |
|---|---|---|
| pooled verbatim rate | 61/84 = **72.6%** | 76/100 = **76.0%** |
| per-run rate mean ± sd | 72.6% ± 10.9 | 75.7% ± 9.0 |
| key facts | 21/25 | 19/25 |
| schema completions | 24/25 | 25/25 |
| wrong source | 0/84 | 0/100 |
| output tokens (5 runs) | 70,990 | 92,507 |
| mean wall per run | 127 s | 133 s |

## Claims

1. **No measured citation-fidelity difference between tiers.** The pooled
   gap (72.6% vs 76.0%) is a third of one within-arm standard deviation;
   per-run rates overlap heavily (haiku spans 56–82%, sonnet 68–91%). n=5
   per arm cannot power an effect this small, and none is claimed.
2. **Zero wrong-source attributions in 184 measured quotes**, both arms —
   the strongest uniform result in the batch.
3. **The tiers fail differently, not unequally** (orchestrator_assertion,
   from reading the absent sets): haiku's absent quotes include agent prose
   written into the quote field on structured pages (2 of 5 runs); sonnet's
   absent quotes are mostly real page content carrying raw HTML entities and
   attributes that break the string match. One synthesizes, the other
   over-quotes markup.
4. **The only hard reliability gap is schema completion**: haiku 24/25
   agents (one StructuredOutput retry-cap failure, run haiku-r1), sonnet
   25/25. The pipeline design already absorbs this failure mode (a null
   result is a visible gap, not silent corruption).
5. **Volume differs**: sonnet produced 19% more measured quotes and 30% more
   output tokens for the same eval — richer context per finding, at the
   corresponding token cost.

Read together with the protocol's rule on both error directions: neither arm
under- or over-attributed sources (claim 2); the misses split between
synthesis (haiku) and markup (sonnet), and a consumer weighing tiers should
weigh those failure modes against their own verification layer, not the
headline rates.

## Deviations and threats

- Records were committed at batch end, not one commit per run (protocol
  step 6 deviation; all records were written to disk immediately per run).
- The arm script was re-frozen once before any successful run (v1 rejected
  stringified args; zero runs recorded under v1).
- `collect.py` gained a `*` phase-map wildcard mid-batch — labeling
  ergonomics, no measurement change.
- Eval weakness discovered mid-batch: tracker `key_fact` conflates fact
  recall with whether the agent restates the bug number in claim text (see
  each record's notes). Affects both arms symmetrically; queued for eval v2.
- Source drift: all cited pages remained reachable and stable across the
  ~40-minute batch window (wrong_source 0 and per-round url_status agree).
- Orchestrator tokens are not captured; totals cover breadth agents only.
