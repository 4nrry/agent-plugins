# Batch 2026-11-11-agy-ask-deny — claims

**Smoke notes, not run records.** Why crew 0.16.2 passes agy deny rules in
`ask`. The live smoke of the same day (`2026-11-11-web-live-smoke-CLAIMS.md`)
found that agy 1.5.5 writes a file in print mode under `--mode plan`, the
only thing `ask` relied on to keep agy read-only. 2026-11-11, agy 1.5.5 with
gemini-3.8-flash at low, its own login; n=1 per case, 9 worker calls.

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
| `ask agy --web --session <id>`, create `probe.txt` on the second turn | the reply quotes the deny rule and gives the word from the first turn |
| `ask agy --cwd <throwaway repository>`: append to `README.md`, delete `notes.txt`, rename `README.md`, with file tools only | the reply quotes the deny rule; both files as they were, `git status` clean |
| `ask agy --web --schema` | ok, the object came back in `structured` |

The verdict's `read_only` ends with "deny rules for write_file, command and
mcp passed through --settings (agy 1.5.5 held to them)", and the 0.16.1
warning is gone for this agy. The real `agy --help` prints on stderr, exits 0
and takes about 0.1 s.

**Checked with stand-ins.** `crew.py --self-test`, 497 checks; fifteen are
for this change. An agy whose help lists the flag (on stderr, as the real
one does) receives exactly the three rules on a first turn, a resumed one
and one with a schema, with and without `--web`, at version 1.5.5 and with
an unreadable version, and gets no warning. One whose help lacks the flag,
has only `--settings-file`, or mentions the word in prose receives none and
keeps the warning. A help that cannot be run counts as no flag. codex is
given no rules. What agy reports as refused lands in the warnings. The
`backends` command lists every backend. Eleven edits that undo one of these
each fail the self-test.

**Cold review.** No defect in the command line, the probe or the warning
logic. It showed that the first tests passed with the help read from stdout
only, with the flag dropped on resumed or schema turns, and with the rules
claimed for other backends; the tests above close those. It also asked for
the resumed-turn and existing-file cases, now in the table.

**Not measured.** Which agy version first has `--settings`: crew asks the
help text each time and does not go by number. A read of a file outside the
working directory, which these rules do not deny. `execute_url`, left
allowed. Whether a rule can be worked around through a tool these three
names do not cover. Whether the session's `permissions` add to the user's
own in `settings.json` or replace them (this machine's file has none). Any
agy but 1.5.5: crew passes the rules to whichever agy lists the flag.
`review` and `delegate` on agy 1.5.5.
