# CLI workers

`scripts/fleet_worker.py` runs the search and extract phases of a deep-research
pipeline on another agent CLI. You keep scope, the 3-vote verify and synthesis.

```bash
python3 scripts/fleet_worker.py check                       # installed backends, tested phases
python3 scripts/fleet_worker.py --self-test
python3 scripts/fleet_worker.py search --backend grok,hermes,agy --question Q --angles angles.json -o search.json
python3 scripts/fleet_worker.py extract --backend opencode --question Q --sources search.json -o claims.json
```

`angles.json` is `[{"label", "query", "rationale"}]`. `extract` reads
`search`'s output directly. With several backends, `--model` takes
`backend=model[,backend=model]`.

## Choosing backends

| Phase | Start with | Avoid |
|---|---|---|
| Search | several engines at once — `grok,hermes,agy` covers xAI and Google indexes | agy alone: it can stall to its print timeout |
| Extract | opencode (free model), grok, or hermes with a page reader | agy: its quotes were mostly not on the page |

Run `check` first: a backend version or phase not in `TESTED` carries a warning
in the output, and needs a smoke run before you trust it.

## What the script enforces

- Each worker runs in an empty temp dir, in its CLI's read-only mode.
- Schemas are closed; arrays are cut to their limit; a quote under 20
  characters fails the item.
- Control, format and bidi code points are stripped from every string a page
  produced.
- Exit 0 never counts: each backend's own success signal is read.
- opencode runs only an allowlist of free models; non-zero-retention terms are
  repeated in the output warnings.
- Search results are merged by URL; `foundBy` lists the engines that agreed,
  and agreement orders sources within a relevance level.

## Backend setup

- hermes needs a page reader to extract: `web.extract_backend` (for example
  `firecrawl`) in `~/.hermes/config.yaml`. It truncates each page to
  `web.extract_char_limit` characters, keeping head and tail; size it to your
  pages.
- opencode's 200k-context free models hold one page; a search loop that
  fetches many pages needs a 1M one.

Measurements behind these choices:
`bench/plugins/agent-fleet/results/2026-10-21-fleet-worker-smoke-CLAIMS.md`
in the source repository.
