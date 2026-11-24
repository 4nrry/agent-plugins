# Batch 2026-11-23-gh-search-firecrawl — claims

**Notes, not run records.** Behind agent-fleet 1.13.0: `references/github-search.md`
and the Firecrawl Local route for blocked hosts. Measured by hand on
2026-11-23 on one Linux laptop, n=1 per item unless a count is given.
That WebFetch refuses reddit.com and stackoverflow.com, and both browsers
reddit.com, is in `2026-10-28-blocked-hosts-youtube-CLAIMS.md`.

**gh search** (gh 2.105.0, authenticated)
- `gh api rate_limit --jq .resources`: `search` limit 30, `code_search` 10,
  per minute. `gh api -i search/code` answered `X-Ratelimit-Resource:
  code_search`.
- `search/repositories?q=stars:>10&per_page=100&page=11` returned 422 "Only
  the first 1000 search results are available", and the call counted.
- `gh search repos --limit 150` returned 150 rows for two search calls.
- `--created`, `--stars`, `--updated` on repos, `--created` on issues and
  `--merged-at` on PRs filtered as documented. `gh search repos --help` has no
  `--pushed` flag; `pushed:` works as query text.
- `gh search code` with `'/Web.*Fetch/'` and with `symbol:NewCmdSearch`
  returned `[]`, exit 0. Plain terms and `--repo`, `--owner`, `--language`,
  `--filename`, `--extension` returned rows.
- A code result's `url` is `github.com/O/R/blob/<commit>/<path>`; its `sha` is
  the blob hash. For `pkg/cmd/search/search.go` in cli/cli,
  `raw.githubusercontent.com` answered 404 with the blob hash and 200 with the
  commit.
- `verify_citations.py --claims`, quote `func NewCmdSearch(f
  *cmdutil.Factory) *cobra.Command {`: ratio 0.0 on the `blob` page, 1.0 on
  the raw URL at the commit.
- Same check on an issue (cli/cli#13840), quote "This issue tracks all no-op
  runs from agentic workflows in this repository.": 1.0 on the
  `github.com/.../issues/N` page and 1.0 on the REST URL.
- The local `gh` token carries `repo`, `workflow`, `admin:org` and
  `delete_repo` scopes.
- The rest of `github-search.md` (256-character and five-operator query cap,
  `in:` scope, legacy code search on the default branch and under 384 KB,
  secondary limits and `retry-after`) is from GitHub's docs, read the same
  day: docs.github.com/en/rest/search/search,
  docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api,
  docs.github.com/en/search-github/searching-on-github, and the gh manual
  at cli.github.com/manual.

**Firecrawl Local 0.1.1** (`cargo install --locked firecrawl-local`, cargo
1.100.0; 8 min, 2.6 GB peak, 23 MB binary; Google Chrome on PATH)
- `scrape`, with `FIRECRAWL_CLOUD=off` and with `auto`: every result below was
  `engine: local-browser` or `local-fetch`, none from the cloud.
- reddit.com/r/docker/: 200, ~56–66k characters with post titles and comment
  links, through the local Chrome, in 4 of 4 runs (both modes, `--browser
  auto` and `always`). With `--browser never`:
  200 and empty markdown.
- stackoverflow.com, the docker tag page and question 23735149: the first
  call to each, both with `off`, returned 403 and empty markdown; the five
  later calls (`auto` on each, then `off`, `auto`, `off` on the question)
  returned 200 with the questions and the accepted answer.
- gnu.org/software/bash: 200 in 0.5 s, ~25 MB peak. npmjs.com package page:
  200. x.com/firecrawl: the login wall. YouTube watch page: the page chrome,
  no spoken words.
- Peak RSS of the `firecrawl-local` process was ~240 MB on pages it rendered
  in Chrome, 25–40 MB on plain fetches (`/usr/bin/time -f %M`).
- `search` with `FIRECRAWL_CLOUD=off` refused: "Web search runs on Firecrawl
  cloud, and the cloud is turned off".
- `firecrawl-local mcp` printed `npm notice run 'firecrawl-mcp'` and listed 31
  tools: it starts the npm MCP server through `npx`.
- Exit code was 0 for blocked and empty results alike. The output is one JSON
  object `{success, data}`; the fields read were `.data.markdown`,
  `.data.metadata.statusCode` and `.data.metadata.engine`. `serve` was not
  run.

**Firecrawl hosted MCP** (`https://mcp.firecrawl.dev/v2/mcp`, no key; server
`firecrawl-fastmcp` 3.41.0)
- `tools/list`: `firecrawl_search`, `firecrawl_scrape`, `firecrawl_parse`.
- reddit.com/r/docker/: "Firecrawl can't scrape this site because it is
  currently not supported", in 0.4 s. stackoverflow.com tag page and gnu.org:
  markdown with the content. YouTube: a Google 401 page as markdown.
- 12 parallel `firecrawl_search` calls: 12 results, no limit hit.
- Not adopted as a route: it adds no host that WebFetch or Firecrawl Local
  could not reach, and every query leaves the machine.
