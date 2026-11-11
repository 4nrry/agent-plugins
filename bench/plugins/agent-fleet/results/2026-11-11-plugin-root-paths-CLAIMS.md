# Batch 2026-11-11-plugin-root-paths — claims

**Notes, not run records.** Why agent-fleet 1.10.1 changes how two scripts
find files. The 0.2.0 audit quoted two rules of the claude.ai plugin
directory's pre-submission checklist: a hook script is held for a reviewer
when it uses paths not written from `${CLAUDE_PLUGIN_ROOT}`, and every file a
script uses should be inside the plugin folder. `hooks/inject.sh` took its
own folder from `BASH_SOURCE`, and `fleet_worker.py` looked for crew.py in
the folder next to its plugin.

**inject.sh.** The skill folder is now `${CLAUDE_PLUGIN_ROOT}/skills/agent-fleet`.
Without the variable a matching prompt gets one stderr line, exit 1 and no
text; a prompt that does not match stays silent.

**Is the variable in a hook's environment.** Read on 2026-11-11, not run:
the Claude Code 2.1.322 binary sets `CLAUDE_PLUGIN_ROOT` and
`CLAUDE_PLUGIN_DATA` on the environment it starts a plugin's hook with, next
to `CLAUDE_PROJECT_DIR`; the routing hook's markers on this machine sit in
the directory Claude Code passes as `CLAUDE_PLUGIN_DATA`, not in the hook's
fallback; and the three bridges under `adapters/` each set
`CLAUDE_PLUGIN_ROOT` to the plugin folder.

**fleet_worker.py.** `find_crew` no longer looks beside its own plugin. It
takes `$CREW_PY`, then `~/.agents/skills/crew`, then Claude Code's plugin
directories. From this checkout, `check` printed the installed copy, and the
checkout's with `CREW_PY` set.

**Tests.** `check_inject_hook.py --self-test` has 32 checks, four of them
new: no variable with and without a match, a variable pointing at a folder
with no skill, and one with a trailing slash. `fleet_worker.py --self-test`
checks that with no `CREW_PY` and an empty HOME crew is not found, although
this repository has a crew plugin beside agent-fleet. The trigger scores of
`2026-10-26-pesquisa-trigger/check_hook.py` are unchanged.

**What this does not settle.** The hooks still use command substitution
(`jq`, `cat`), `$HOME` and `$CLAUDE_PLUGIN_DATA`, which the same checklist
names, and fleet_worker still runs a script of another plugin. Whether a
reviewer holds the plugin for those is theirs to say. The new hook was not
run inside a live Claude Code session.
