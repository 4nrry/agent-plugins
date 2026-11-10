# Batch 2026-11-10-three-audits — claims

**Notes, not run records.** What extension-audit 0.2.0 found when it was run in
full on three plugins of this repository, on 2026-11-10: media-agent 0.18.1,
agent-fleet 1.9.1 and crew 0.15.3. One run per plugin, so nothing here is a
rate, and no run without the skill was made to compare with.

**How it was run.** One headless Claude Code 2.1.322 session per plugin
(`claude -p`, Opus 5.5 at xhigh effort), with the skill loaded from the
checkout through `--plugin-dir` and no tool that can write: Read, Grep, Glob,
the Skill tool, and Bash limited to the linter, `claude plugin validate`,
`--self-test` and `--help`. The prompt asked for the skill's whole workflow,
for every file to be read in full, and for one extra check the checklist does
not carry: whether each SKILL.md and README matches what its scripts do.

| Plugin | Errors | Warnings | Notes | Turns | Wall time | Cost the CLI reported |
|---|---|---|---|---|---|---|
| media-agent | 1 | 8 | 16 | 44 | 602 s | US$ 11.21 |
| agent-fleet | 0 | 10 | 18 | 30 | 528 s | US$ 8.97 |
| crew | 2 | 7 | 18 | 35 | 476 s | US$ 9.82 |

The cost is the session's own figure at API prices; the runs went through a
subscription login.

**What the mechanical steps found.** Nothing: the linter and the validator
reported only the missing icon on all three, which was already known. All 80
findings came from the reading.

**What the findings were.** Most were a document saying what its script does
not do, the check added in the prompt. The three errors:

- crew documented `--web` as web search and fetch only for six backends and
  said so in the verdict; three of them keep reading the working directory.
- crew's skill said to run commands from the skill's directory, while the
  commands take the current directory as the repository to work on.
- media-agent's turntable skill promised a fallback from OptiX to CUDA that the
  script did not have; with no device it rendered on the CPU without a line.

One finding was reproduced before it was fixed: both prompt hooks piped the
prompt into `grep -q` under `pipefail`, so a prompt of a few thousand lines
with the trigger near the top matched nothing (60,000 filler lines: no output
before the fix, the expected output after).

**What was done with them.** Each finding was checked in the code before it
was acted on, and none of those checked was false. 71 were fixed, in
media-agent 0.18.2, agent-fleet 1.9.2 and crew 0.15.4. 9 were left as the
owner's decisions: whether crew should enforce web-only instead of describing
it, splitting `crew.py`, crew's ZCode section and a sample verdict, a
per-session marker for agent-fleet's injection hook, two of its path lookups,
media-agent registering Kinocut as an MCP server while teaching its CLI, the
`audio` skill owning stock footage, and OpenAI's directory.

**A defect in the linter itself.** The media-agent run noticed that, from a git
worktree, the linter skipped every reference file in silence: it matched its
skip list against absolute path parts, and the checkout sat under
`worktrees/`. Fixed in extension-audit 0.2.1. A run outside the worktree then
showed two missing tables of contents the worktree run had hidden.

**The fixes were reviewed too.** A second model read each fix cold. It found
no bug in agent-fleet's, one sentence the code contradicted in crew's, and one
real gap in media-agent's (two inputs that still exited 1 where the new
contract says 2). All were corrected before merging.

**Not measured.** Whether a cheaper model or a lower effort finds the same
things; how many findings a second run would repeat; how many real defects all
three runs missed. No worker CLI, GPU job or network service was run, so every
statement about those was checked against code, not behavior.
