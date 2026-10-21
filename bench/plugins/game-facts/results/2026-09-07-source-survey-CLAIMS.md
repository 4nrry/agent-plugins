# Batch 2026-09-07-source-survey — claims

**Notes, not run records.** Imported from the survey that shaped the
`game-versions` skill: no record conforms to `bench/schema/run.schema.json`, and
source metadata was judged by agents, not checked by hand. These notes back
the skill's source rules as design evidence; they support no with/without
comparison and no improvement claim.

**Setup.** One game (Palworld), one day (2026-09-07, hours after patch
v1.0.4), 10 question archetypes, 22 agents, 80 sources with per-source
metadata, adversarial verification against the official v1.0.4 notes.

| Source type | n | dated | states version | after the patch |
|---|---|---|---|---|
| hosting blog | 22 | 77% | 64% | 0 |
| wiki | 16 | 88% | 56% | 3 |
| games site | 14 | 100% | 79% | 2 |
| official | 12 | 67% | 92% | 3 |
| forum | 12 | 100% | 17% | 0 |
| reddit | 2 | 0% | 0% | 0 |
| all | 80 | 84% | 59% | 8 |

**Findings the skill rests on**

- Reading the changelog first invalidated content in 10 of 10 categories (53
  named items); about a quarter were bug fixes, where the source honestly
  measured a broken build.
- "Dated" did not mean fresh: 84% were dated, 90% predated the patch.
- Majority vote resolved 0 of 41 contradictions; the largest agreement cluster
  was one source copied by five domains.
- The 14-source category got the worst verdict; the 10-source category with 3
  post-patch sources was the only one with a confirmed claim.
- Wiki pages carried version provenance in their content, which let the
  verifier reject two wiki pages; no official source answered a meta question.
- Reddit returned no real thread in 10 of 10 categories; `site:reddit.com` was
  replaced by `steamcommunity.com` in at least 7; Fandom returned HTTP 402 in
  2 of 2.

**Video captions** (issue #6, 2026-09-07): `--sub-lang en` misses tracks that
exist only as `en-en` in the automatic pool; no-install routes return HTTP 200
with an empty body; joining caption segments with `"".join()` lost 5 of 39 words
on one track and none on another; yt-dlp's warning changed between 2026-08-18
and 2026-09-07 on the same version. Proper names survived ASR (`Anubis` 28x),
but transcripts carry numbers with no version anchor.

**Steam news feed** (2026-09-07): `GetNewsForApp` for appid 1623730 returned
`v1.0.4: Balance Adjustments & Bug Fixes` by `pocketpair_dev`, dated the same
day as the manifest's `LastUpdated`; the feed mixes press items; the dedicated
server's appid returns no items.

**Limits.** One game, one day, right after a patch, which overstates staleness.
No question was LOCAL, so the local branch is derived, not measured. The
verifier was told to mark stale when in doubt.

**First real use (2026-09-08).** An 11-agent run on one question: 23 sources,
none after the previous day's patch. The local `.ini` held the deciding values
(1.5x and 2.0x multipliers) and reversed the recommendation. It exposed two
gaps, since fixed in the skill: the patch fence had no exit when every source
predated a day-old patch (18 of 18 failed), and no rule caught one source
disguised as consensus.
