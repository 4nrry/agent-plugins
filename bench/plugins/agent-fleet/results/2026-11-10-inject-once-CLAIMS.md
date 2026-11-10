# Batch 2026-11-10-inject-once — claims

**Notes, not run records.** Why agent-fleet 1.10.0 injects the skill once per
session. Measured on 2026-11-10 on one Linux laptop with bash 5 and jq, by
piping `UserPromptSubmit` JSON into `hooks/inject.sh`. No model was run.

**Size.** Before, every matching prompt printed the whole SKILL.md: 8,272
bytes with the header line. Now the first match in a session prints the same
8,272 bytes and each later one 551 bytes (the path is this checkout's, so the
count moves with the install path).

**What the pointer keeps.** The matched reason, the path of SKILL.md with an
instruction to read it if its text is no longer in context, and the routing
rule, which the hook already called the one most often skipped.

**Fixture test.** `scripts/check_inject_hook.py --self-test`, 22 checks:
whole text on the first match, pointer on the second and third, whole text in
another session, whole text again after `--forget`, whole text every time
with no session id, with a session id that is a path, and with a data
directory that cannot be created; nothing on a miss or on input that is not
JSON; the trigger still found above 60,000 filler lines. Against the 1.9.2
hook the same test fails 4 checks. The trigger scores of
`2026-10-26-pesquisa-trigger/check_hook.py` did not move (its payloads carry
no session id).

**Not measured.** Whether Claude Code runs the `SessionStart` entry with
matcher `compact|clear` and the same session id the prompts carry: the hook
was fed by hand, not by a live compaction. If it does not, the marker stays
and the pointer is what tells the model to read the file again. Whether a
model follows that pointer after a compaction was not tested either.
