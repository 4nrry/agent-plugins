# Batch 2026-10-26-opencode-zen-refresh — claims

**Smoke notes, not run records.** n=1 per model, opencode v2.1.4.

- `opencode models` listed eight free models: beam, deepseek-v4.1-flash,
  flint-40b, glm-5.3-flash, mimo-v2.6-flash, nemotron-3-ultra,
  nemotron-3.5-lightning and nemotron-3.5-super-vl. minimax-m3.1-flash, still in
  crew's allowlist, was gone.
- `crew.py ask opencode "In one sentence: what does the Unix command 'tee'
  do?" --model opencode/<m>` answered correctly with `beam-free` (3 s) and
  `flint-40b-free` (4 s). `nemotron-3-ultra-free` failed twice, 20 s apart:
  `provider.invalid-request`, "Upstream request failed: Model is unavailable."
  (400), so it stays out of the allowlist.
- Zen's docs, read the same day: deepseek and glm are zero-retention and
  no-training; beam does not train and keeps data 30 days; flint and mimo may
  train while free; the Nemotron models are logged by NVIDIA ("do not submit
  personal or confidential data").
- GitHub's plans page: "Copilot Free and Copilot Student both have an
  allowance of AI credits", and both offer only auto model selection. crew's
  note that Free had no free quota was wrong.
