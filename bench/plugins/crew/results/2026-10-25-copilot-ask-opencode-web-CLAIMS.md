# Batch 2026-10-25-copilot-ask-opencode-web — claims

**Smoke notes, not run records.** GitHub Copilot CLI 1.0.103 (`--model auto`,
routed to gpt-5.6-luna) and opencode 2.1.4 (`deepseek-v4.1-flash-free`); n=1
per case. Logs stayed in the session scratchpad and were not committed.

## Copilot

| Case | Result |
|---|---|
| `ask`, then `ask --session` | "pong", then "kumquat" from the first turn |
| `review --backend copilot --diff HEAD~1` (guarded path) | ok in 38 s, 0 findings on a docs-only diff |
| `delegate`, the slugify task | ok in 16 s, gate green on the first try, report `done`; one denial, the `skill` tool (a user skill), which is outside the allowlist |
| raw `--output-format json` | `result` carries `sessionId` and `usage.premiumRequests`; `session.usage_checkpoint` carries `totalNanoAiu`; `write_bash` is reported as an unknown tool name |

Consequences: the parser returns the session and usage (with `ai_credits`),
a run without a `result` event fails, `write_bash` left the exclusion list,
and 1.0.103 is the tested version.

## opencode web search

| Observed | Consequence |
|---|---|
| `websearch` ends with "Web search cancelled" and the run exits 1 | the cause, in the 2.1.4 bundle: with no provider saved (`websearch:provider` in the `kv` table of `opencode.db`), the tool asks the user; `run` cancels the question |
| a 2.x plugin calling `ctx.websearch.transform((w) => w.default.set("exa"))` | the search completes, exit 0; the choice lives in memory for the run |
| `opencode api websearch.query` with `providerID: "exa"` and no key | results returned |

After the fix: `ask opencode --web` ok in 11 s with a cited answer;
`fleet_worker.py search --backend opencode`, 2 angles, 2/2 ok, 9 sources; a
two-turn `ask` ok on 2.1.4.

Two runs hung at server start for the whole timeout between 01:16 and 01:22
UTC, with and without a plugin; the same commands then finished in 2–5 s.
opencode.md already lists hangs at start.
