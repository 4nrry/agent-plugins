# Batch 2026-11-11-agy-ask-deny — claims

**Smoke notes, not run records.** Why crew 0.16.2 passes agy deny rules in
`ask`. The live smoke of the same day (`2026-11-11-web-live-smoke-CLAIMS.md`)
found that agy 1.5.5 writes a file in print mode under `--mode plan`, the
only thing `ask` relied on to keep agy read-only. 2026-11-11, agy 1.5.5 with
gemini-3.8-flash at low, its own login; n=1 per case, 4 worker calls.

**What agy 1.5.5 offers.** Read from `agy --help`, its changelog and the
text in its binary, not from a manual: `--settings`, "settings for this
session only, never saved: a JSON object of settings.json keys, inline or as
a file path"; permission rules written `write_file(...)`, `read_file(...)`,
`command(...)`, `mcp(...)`, `execute_url(...)`; and a changelog line saying
explicit deny rules still apply in headless runs.

**The rule, tried directly.** In a scratch directory, with crew's usual
flags plus `--settings '{"permissions":{"deny":["write_file(*)","command(*)"]}}'`,
agy asked to create `probe.txt` answered "Permission denied for
write_file(<path>). Matches user-configured deny rule." and the directory
stayed empty. The same request without the rule had written the file.

**Through crew 0.16.2**, which passes `write_file(*)`, `command(*)` and
`mcp(*)` when `agy --help` lists the flag:

| Call | Result |
|---|---|
| `ask agy --web`, a question with one web search | ok in 25.2 s; no denied action in agy's output; 78,067 input tokens against 30,473 for the same question before the rules, so a page was read |
| `ask agy --web`, create `probe.txt` | the reply quotes the deny rule; no "left files" warning |
| `ask agy --cwd <throwaway repository>`, create `probe.txt` | the reply quotes the deny rule; the repository holds only its README, `git status` clean |

The verdict's `read_only` ends with "--settings denies write_file, command
and mcp for the session", and the 0.16.1 warning is gone for this agy.

**Checked with stand-ins.** `crew.py --self-test`, 487 checks; five are for
this change: an agy whose help lists the flag receives exactly the three
rules, with and without `--web`, at version 1.5.5 and with an unreadable
version, and gets no warning; one whose help does not list it receives no
flag and keeps the warning. Four edits (the flag never passed, passed
without asking the help, the warning kept, `write_file` dropped from the
rules) each fail the self-test.

**Not measured.** Which agy version first has `--settings`: crew asks the
help text each time and does not go by number. A read of a file outside the
working directory, which these rules do not deny. `execute_url`, left
allowed. Whether a rule can be worked around through a tool these three
names do not cover. `review` and `delegate` on agy 1.5.5.
