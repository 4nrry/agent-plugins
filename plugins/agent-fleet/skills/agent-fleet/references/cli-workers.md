# CLI workers

`scripts/fleet_worker.py` runs the search and extract phases of a deep-research
pipeline on another agent CLI. You keep scope, the 3-vote verify and synthesis.

Every worker turn goes through the **crew** plugin: `crew.py ask <backend> --web
--schema`. crew owns each CLI's flags, its read-only web profile, isolation, the
opencode model allowlist, output parsing and version warnings. This script owns
the research: prompts, schemas, sanitizing, merging and ranking. crew must be
installed; it is found through `~/.agents/skills/crew` or in Claude Code's
plugin copies, and `CREW_PY` overrides both. Where crew is installed
elsewhere, or to use a repository checkout's copy, set `CREW_PY` to that
`crew.py`; `check` prints the one in use.

```bash
python3 scripts/fleet_worker.py check                       # crew's path and the web-capable backends
python3 scripts/fleet_worker.py --self-test
python3 scripts/fleet_worker.py search --backend grok,agy,opencode --question Q --angles angles.json -o search.json
python3 scripts/fleet_worker.py extract --backend opencode --question Q --sources search.json -o claims.json
```

`angles.json` is `[{"label", "query", "rationale"}]`. `extract` reads
`search`'s output directly. Each backend runs crew's `--tier` (default
`cheap`) at **low** effort, since both phases are long tool loops, whatever
effort crew's tier carries for general work. A backend whose tier sets no
effort (opencode) gets none. `--model` overrides the model, as
`backend=model[,backend=model]` with several backends, and keeps that model's
own effort; `--effort` sets one effort for every backend.

## The worker's temporary directory

Each turn runs from `/tmp/fleet-worker-<random>/`, which holds the prompt, the
schema and an `.ai-memory.toml` marker (`workspace = "default"`, `project =
"fleet-workers"`), and is removed afterwards. Without the marker, ai-memory
names a project after the folder, so every run left one behind; outside the
home it reads a marker only in the working directory itself, never a parent's,
which is why the file is in each directory and not above them. crew writes the
same marker in its own `--web` directory (agy, opencode and codex run there,
not in this one), so by default one project holds both.

`FLEET_WORKER_AI_MEMORY_PROJECT=<name>` renames the project (letters, digits,
`.`, `_`, `-`; up to 64) and is passed on to crew as `CREW_AI_MEMORY_PROJECT`;
`off`, or an empty value, writes no marker in either directory. Set it, not
`CREW_AI_MEMORY_PROJECT`, to move a fleet run: with it unset crew's directory
follows whatever `CREW_AI_MEMORY_PROJECT` says. A name that is not valid
writes none and the result's `warnings` say so. The file is plain
TOML and does nothing for anyone who does not use ai-memory.

## Choosing backends

Web-capable in crew: grok, agy, hermes, codex, claude (from a host that is not
Claude), opencode.

| Phase | Start with | Avoid |
|---|---|---|
| Search | several engines at once: `grok,agy,opencode` covers xAI's, Google's and Exa's indexes, opencode at no cost | grok and hermes together: on an xAI login they search the same index |
| Search on X (posts, announcements, people, threads) | grok, hermes: the only engines here that read X | engines without X access, which return press coverage of a post instead of the post |
| Extract | opencode (free model), grok, or hermes with a page reader | agy: its quotes were mostly not on the page |

Spread a fan-out across vendors, not across CLIs. grok, hermes logged in to
xAI, and cursor on a Grok model all draw one X Subscription pool, so splitting
work among them adds no quota; agy, opencode and codex each spend their own.

crew's warnings (a backend or version never run end to end) are carried into
the output; treat them as a reason for a smoke run before trusting the result.

## What the script enforces

- Schemas are closed; arrays are cut to their limit; a quote under 30
  characters fails the item, the length below which `verify_citations.py`
  does not score a quote.
- Control, format and bidi code points are stripped from every string a page
  produced.
- A worker whose crew verdict fails, or that returns no object, is reported per
  item with its reasons, never dropped.
- Search results are merged by URL; `foundBy` lists the engines that agreed,
  and agreement orders sources within a relevance level.

## Backend setup

- hermes needs a page reader to extract: `web.extract_backend` (for example
  `firecrawl`) in `~/.hermes/config.yaml`. It truncates each page to
  `web.extract_char_limit` characters, keeping head and tail; size it to your
  pages.
- opencode's free models rotate in Zen; crew's `cheap` tier for opencode names
  the one to use, and `crew.py backends` shows it.

Check what `extract` returns with `python3 scripts/verify_citations.py --claims
claims.json`: it scores each quote against its own `sourceUrl`.

Measurements behind these choices:
[bench/plugins/agent-fleet/results/](https://github.com/4nrry/agent-plugins/tree/main/bench/plugins/agent-fleet/results).
