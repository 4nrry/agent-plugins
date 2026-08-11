# Benchmark protocol

Rule zero of this repository: **a claim that a plugin improved is a comparison
between run records committed under `bench/results/`.** A claim without run
records is marketing, and does not go in a README, a description, or a commit
message.

## Definitions

- **Run**: one execution of a task under fixed conditions, producing one
  record conforming to `schema/run.schema.json`.
- **Arm**: a set of runs sharing all conditions. Two arms differ in exactly
  one declared variable.
- **Phase**: a named stage of the pipeline (e.g. `breadth`, `verify`,
  `adversarial`, `synthesis`). Every agent in a run is attributed to one.
- **Agent record**: per-agent measurements — model, token counts split by
  kind (output, uncached input, cache write, cache read), tool calls, wall
  duration, and a SHA-256 of the exact prompt.

## Procedure

1. **State the question and the single variable** before running anything.
   Write them into the run records (`question`, `variable`, `arm`).
2. **Freeze the eval set** under `bench/evals/` before the first run: inputs,
   expected outcomes, and mechanical assertions (see `evals/example.json` for
   the required shape). Record its sha256 in every run (`eval_sha256`).
   Changing the eval set starts a new benchmark; results across eval versions
   are not comparable, and the hash is what catches a silent edit.
3. **Launch arms paired, in the same turn**, with prompts identical except
   the variable. Give every run of the comparison the same `batch_id`, and
   store `orchestrator_prompt_sha256` in each record — pairing that cannot be
   checked mechanically is pairing on trust. Sample size: at least 5 runs per
   arm for outcome comparisons; at least 3 repetitions per query for rate
   measurements. These are floors, not targets — report the n you used.
4. **Collect immediately.** Run `collect.py` on each workflow transcript
   directory as soon as the run completes. The directory is printed by the
   Workflow tool at launch ("Transcript dir: …") and lives at
   `~/.claude/projects/<project-slug>/subagents/workflows/<workflow_run_id>/`.
   Task-level summaries live in ephemeral tmp storage and do not survive a
   restart (measured: one restart, one loss); agent transcripts under the
   project directory are durable and carry richer data (per-call cache
   splits, resolved model IDs).
5. **Verify mechanically what can be verified mechanically** — string checks
   for citations, scripts for assertions — and record the verifier's own
   self-test result in the run record. A verifier that was not self-tested
   contributes opinions, not measurements.
6. **Commit one JSON per run**, named `<date>-<slug>-<arm>-r<n>.json`, in the
   same change as the plugin version it measured.
7. **Tag every outcome with its source.** Each sub-object of `outcomes`
   carries `"source": "script"` (mechanically measured by a self-tested
   verifier) or `"source": "orchestrator_assertion"` (counted or judged by
   the orchestrator). The two trust tiers never mix in one sub-object — a
   narrative rescue of a failed mechanical check must not be summable with
   the measurement it contradicts.
8. **Write claims as comparisons.** Cite run IDs. Report both error
   directions (misses and over-flags), not a single accuracy number. Anything
   in the claim that is not in the records is labeled estimated or inferred.

## Imported records

Measurements that predate this protocol, or that came out of a foreign harness,
may be committed under `bench/results/` on three conditions: the raw output is
published **byte-identical** with its sha256 stated (a retrofit into this
schema would be a rewrite of data that cannot be re-derived); the record's
claims file lists every field the schema requires and the harness did not
emit; and no claim is made that those missing fields would have supported —
a batch without token accounting cannot carry a cost claim. Imported records
are labeled as such in their first paragraph.

## What the token split is for

Cost claims need `tokens.output`, `tokens.input_uncached`,
`tokens.cache_write`, and `tokens.cache_read` per agent, because the four are
priced differently and cache dominates long tool loops. A single total hides
exactly the number a routing decision needs. Cost in currency is computed at
read time from current published prices — never stored in records, because
prices expire.

## Threats to validity — standing, not per-run

- **Small n.** The floors above separate systematic error from noise; they do
  not power subtle effects. A one-in-twenty difference at n=5 is a tie.
- **The ruler is part of the apparatus.** Consensus answer keys formed under
  one pipeline configuration can stop being unanimous under another
  (measured). Treat disagreement with the key as data about both.
- **Sources drift.** Web-dependent evals cite pages that change. Records
  store what the verifier fetched and when.
- **Models drift.** Records store exact model IDs and the harness version;
  comparisons across model updates are labeled as such.

## Current gaps

Recorded here so they read as untested rather than covered:

- Agents launched outside a workflow (e.g. a single adversarial pass via the
  Agent tool) have no transcript directory harvested by `collect.py` yet;
  they enter records under `untracked_agents`, and every total that excludes
  them is a lower bound.
- Orchestrator (main-context) tokens are not captured per run.
- One paired comparison exists under this protocol (`2026-08-07-breadth-tier`,
  n=5 per arm); the `2026-08-06-plasma67-pilot` record is n=1 and supports no
  comparison claims. Everything else the plugin asserts is still untested here.
- The trigger-eval batch is imported (see above): it carries no token or
  timing data, so the plugin's hook is justified by a recall measurement and
  by nothing about its cost.
- Usage accounting was verified against one harness build's transcript format
  (progressive streaming snapshots per `message.id`); a format change would
  need re-verification, which is why `harness.claude_code_version` is
  required.
