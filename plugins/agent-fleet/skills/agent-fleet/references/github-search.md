# Searching GitHub with gh

When a question is about repositories, code, issues, pull requests, releases
or users on GitHub, search through `gh` rather than WebSearch: it answers
from the API with filters and dates, where a web search returns listicles and
stale star counts. Measured with gh 2.105.0 on 2026-11-23; the record is
`2026-11-23-gh-search-firecrawl-CLAIMS.md` under
[bench/plugins/agent-fleet/results](https://github.com/4nrry/agent-plugins/tree/main/bench/plugins/agent-fleet/results).

## Which command

| Question | Command |
|---|---|
| Which repos exist for X | `gh search repos X --stars ">=50" --updated ">2026-06-01" --sort stars --json fullName,url,stargazersCount,pushedAt,description,license --limit 30` |
| Where in code is X | `gh search code X --repo O/R` (or `--owner`, `--language`, `--filename`, `--extension`) `--json path,url,repository,textMatches` |
| What people reported or changed | `gh search issues X --repo O/R --state closed --created ">=2026-01-01"`, `gh search prs X --merged-at ">=..."` |
| How many match | `gh api -X GET search/repositories -f q='X stars:>50' -f per_page=1 --jq .total_count` (one call, no rows) |
| Releases, a file, an issue body | `gh api repos/O/R/releases`, `gh api repos/O/R/contents/PATH`, `gh api repos/O/R/issues/N` |

- Always pass `--json <fields>` and `--limit N`; the default text output is
  for people. Ask only for fields you will read.
- Qualifiers can go in the query as text (`language:python pushed:>2026-09-01`)
  or as flags (there is no `--pushed` flag; write `pushed:` in the query);
  dates are `YYYY-MM-DD` with `>`, `>=`, `<`, `..`. Put `--`
  before a query that starts with a negation (`-- -topic:demo`).
- A repo search without `in:` matches name, description and topics only; add
  `--match readme` (or `in:readme`) to search READMEs.
- `gh search code` runs GitHub's legacy code search: default branch only,
  files under 384 KB, and at least one plain term. Regex (`/a.*b/`) and
  `symbol:` return `[]` with exit 0, not an error, so an empty result after
  either means nothing. To search with them, ask the user to run the query on
  github.com.

## Limits

- Search has its own buckets: 30 calls a minute for repos, issues, PRs,
  commits and users, and 10 a minute for code. `gh api rate_limit --jq
  .resources.search,.resources.code_search` shows what is left and costs
  nothing.
- Only the first 1,000 results of a query exist. Asking past them is a 422,
  and the failed call still counts. Narrow the query (a date range, a star
  floor) instead of paging deeper.
- `--limit` costs one call per 100 rows: `--limit 150` is two calls.
- A query longer than 256 characters, or with more than five AND/OR/NOT, is a
  422.
- In a fan-out, the bucket is shared by every agent on the same token. Keep
  GitHub searches to one agent, or at most three at once, and code search
  under eight calls a minute. On a 403 or 429, wait for `retry-after`, or a
  full minute when there is none.

## Citing what gh found

`verify_citations.py` fetches the cited URL and string-matches the quote:

- Code: cite `https://raw.githubusercontent.com/O/R/<commit>/<path>`. Take
  `<commit>` from the 40-character segment after `/blob/` in the result's
  `url`, not from its `sha` field, which is the file's blob hash and gives a
  404 there. A quote cited to the `github.com/.../blob/...` page scored 0.0:
  that page renders the code with scripts.
- Issues and PRs: the `github.com/O/R/issues/N` page scored 1.0 on a plain
  sentence of the body. Quote prose, not markdown syntax.
- Repo facts (stars, last push, licence): they change daily. Cite the repo URL
  and the date you read them; there is no quote to match.

## Read-only

The token `gh` uses usually carries write scopes (`repo`, `workflow`, often
`delete_repo`). A worker that can run `gh` can write. Give a GitHub search
agent only `gh search` and `gh api -X GET` through the toolset's allowlist, or
run the searches yourself and hand the agents the results; a sentence telling
it not to write is not a control.
