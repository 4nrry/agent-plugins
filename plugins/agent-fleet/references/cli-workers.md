# CLI workers

`scripts/fleet_worker.py` runs the search and extract phases of a deep-research
pipeline on another agent CLI. You keep scope, the 3-vote verify and synthesis.

Every worker turn goes through the **crew** plugin: `crew.py ask <backend> --web
--schema`. crew owns each CLI's flags, its read-only web profile, isolation, the
opencode model allowlist, output parsing and version warnings. This script owns
the research: prompts, schemas, sanitizing, merging and ranking. crew must be
installed; it is found as a sibling plugin, through `~/.agents/skills/crew`, or
in Claude Code's plugin copies, and `CREW_PY` overrides all of them.

```bash
python3 scripts/fleet_worker.py check                       # crew's path and the web-capable backends
python3 scripts/fleet_worker.py --self-test
python3 scripts/fleet_worker.py search --backend grok,hermes,agy --question Q --angles angles.json -o search.json
python3 scripts/fleet_worker.py extract --backend opencode --question Q --sources search.json -o claims.json
```

`angles.json` is `[{"label", "query", "rationale"}]`. `extract` reads
`search`'s output directly. Each backend runs crew's `--tier` (default
`cheap`); `--model` overrides it, as `backend=model[,backend=model]` with
several backends, and `--effort` sets the effort.

## Choosing backends

Web-capable in crew: grok, agy, hermes, codex, claude (from a host that is not
Claude), opencode.

| Phase | Start with | Avoid |
|---|---|---|
| Search | several engines at once: `grok,hermes,agy` covers xAI and Google indexes; opencode adds Exa's index at no cost | — |
| Extract | opencode (free model), grok, or hermes with a page reader | agy: its quotes were mostly not on the page |

crew's warnings (a backend or version never run end to end) are carried into
the output; treat them as a reason for a smoke run before trusting the result.

## What the script enforces

- Schemas are closed; arrays are cut to their limit; a quote under 20
  characters fails the item.
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

Measurements behind these choices: `bench/plugins/agent-fleet/results/` in the
source repository.
