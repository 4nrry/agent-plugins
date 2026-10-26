#!/usr/bin/env python3
"""Check a report's quotes against the pages it cites.

WHY THIS EXISTS
---------------
Every fleet that produces source-grounded claims needs this check, and it gets
rewritten from scratch every time. In nine measured runs of the same research
task, seven orchestrators independently wrote their own version — and at least
one of them shipped a broken control test without noticing.

Rewriting it is not the expensive part. Getting it right is. Each of the traps
below silently turns a true quote into an apparent fabrication, which is worse
than no check at all: it makes you correct something that was already correct,
or accuse an agent that did its job.

THE SEVEN TRAPS, ALL PAID FOR ALREADY
-------------------------------------
1. Line-wrapped quotes. A single-line `grep -F` misses a sentence that HTML
   broke across lines. Fixed by collapsing all whitespace before comparing.
2. Markdown inline markup. The agent writes `--flag` with backticks; the source
   page has none. A quote that was verbatim scored 0.625.
3. Over-eager stripping. Removing `~` to kill `~~strikethrough~~` also removed
   the `^~` operator that the claim under test was about.
4. Attribution lines inside the quote. `— <https://...>` on the next line of
   the same blockquote dilutes the ratio with ~70 characters that can never
   match; a 250-character verbatim passage scored 0.53.
5. Report prose in quotation marks. When the report is written in one language
   and the sources are in another, the report's own quoted words get measured
   against the page and "fail".
6. Ambiguous stopwords. `no` and `do` are English *and* Portuguese, so using
   them to detect language made foreign prose read as English.
7. Attribution by proximity. Crediting each quote to the nearest URL breaks on
   a report that opens a section with one URL and then cites two pages inside
   it — this produced 14 false "wrong source" hits on a report whose citations
   were all correct. Fixed by scoring against every URL in the same section.

WHAT IT MEASURES
----------------
A match ratio, not pass/fail. Near 1.0 the quote is there; near 0.5 or below
the agent wrote from memory. Plus the argmax: which cited page matches best.
When the best page is not one the section offers, that is a real quote on the
wrong source — the failure that survives a reading review and that only this
check catches.

Ratios only carry information above roughly a sentence. Three tokens will match
somewhere on almost any page, including the paragraph that does not support the
verdict, so a high ratio on a short quote proves presence, not anchoring.

USAGE
-----
    python3 verify_citations.py REPORT.md -o result.json
    python3 verify_citations.py --self-test

Run the self-test first. It takes two seconds and proves both ends: a true
quote broken across five lines scores 1.0, and an invented one stays below 0.4.
"""

import argparse
import gzip
import json
import re
import sys
import unicodedata
import urllib.error
import urllib.request
from pathlib import Path
import zlib

UA = "Mozilla/5.0 (X11; Linux x86_64) verify_citations/1.0"
TIMEOUT = 30
MAX_BYTES = 4_000_000

SHINGLE = 20  # comparison window, in normalized characters
STEP = 8      # stride between windows


# --------------------------------------------------------------- normalizing

_CURLY = {
    "‘": "'", "’": "'", "‚": "'", "‛": "'",
    "“": '"', "”": '"', "„": '"', "‟": '"',
    "–": "-", "—": "-", "−": "-", " ": " ",
    "…": "...",
}


def normalize(text: str) -> str:
    """Flatten the differences that should not count: markup, line breaks,
    typographic quotes, case.

    Two of these matter more than the rest, and both were found by breaking the
    self-test:

    - Collapsing whitespace. Without it, a true quote that HTML wrapped across
      lines does not match, and becomes a false accusation of fabrication.
    - Removing markdown inline markup. The agent quotes with backticks and
      asterisks the source page never had; a quote that was present on the page
      scored 0.625 purely because of the backticks around a formatted term.

    Applied to both sides, so the comparison stays fair.
    """
    text = unicodedata.normalize("NFKC", text)
    for a, b in _CURLY.items():
        text = text.replace(a, b)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)  # [text](url) -> text
    # Only the unambiguously-markdown forms. A lone `*` or `~` stays: both are
    # real syntax in nginx config and in regexes, and one corpus claim was
    # about the `^~` modifier itself — stripping the tilde would erase the very
    # thing under discussion.
    text = re.sub(r"`+", "", text)                    # code spans
    text = text.replace("**", "").replace("~~", "")   # bold, strikethrough
    text = re.sub(r"\s+", " ", text)
    return text.strip().lower()


# Sources are usually English-language docs while the report may be written in
# the user's own language. Counting function words from each side separates a
# quotation of the source from the report's own prose in quotation marks.
#
# `no` and `do` are deliberately absent from the English list: they are also
# Portuguese words, and while they were in it, foreign prose counted as English
# and was reported as a fabricated quote.
#
# Adapt _OTHER_STOP to whatever language the report is written in. When report
# and sources share a language this filter is a no-op, and the report's own
# quoted words may be counted as candidates — a known limitation, visible as
# low-ratio entries that are obviously the report talking to itself.
_EN_STOP = re.compile(
    r"\b(the|of|is|are|to|and|that|for|with|not|this|be|will|when|if|as|it|by"
    r"|from|on|in|its|which|can|has|have|been|any|all|each|does)\b", re.I)
_OTHER_STOP = re.compile(
    r"\b(que|n[ãa]o|uma|para|com|aquele|aquela|numa|num|pelo|pela|sem|sobre"
    r"|mais|mas|seu|sua|isso|ele|ela|acontece|chave|prefixo|caso|entre|quando"
    r"|onde|porque|ent[ãa]o|assim|ainda|s[óo]|j[áa]|dos|das|pelos|pelas)\b",
    re.I)


def looks_like_source_quote(q: str) -> bool:
    """English in the majority, and at least TWO English markers.

    A simple majority was not enough: `Built-in Operator Classes` carries an
    `in` that matches as an English function word, which let foreign prose with
    one technical term in it pass as a source quote and fail as fabricated. A
    zero-to-zero tie is a configuration block, not quoted prose, so it is also
    excluded.
    """
    en = len(_EN_STOP.findall(q))
    return en >= 2 and en > len(_OTHER_STOP.findall(q))


# The attribution line lives INSIDE the same blockquote as the quote:
#     > "REINDEX CONCURRENTLY can rebuild an index ..."
#     > — https://www.postgresql.org/docs/release/12.0/
# Leaving it in the compared text dilutes the ratio with characters that can
# never match. The angle-bracket form is mandatory to accept: reports write
# `— https://x`, `— <https://x>` and `— [text](https://x)` interchangeably, and
# without the angular case a 250-character verbatim passage scored 0.53.
_ATTRIB_LINE = re.compile(
    r"(?m)^\s*[—–\-]\s*(?:<?https?://[^\s>]+>?|\[[^\]]*\]\([^)]*\)).*$")

# Parenthesised attribution, at the end or mid-line: `(<https://...>)`
_ATTRIB_PAREN = re.compile(r"\(\s*<?https?://[^)\s]+>?\s*\)")

# Blockquote marker on a continuation line. A quoted passage that spans several
# blockquote lines carries the `>` characters along, and each one lowers the
# match ratio without the agent having done anything wrong.
_BQ_PREFIX = re.compile(r"(?m)^[ \t]*>[ \t]?")


def clean_quote(q: str) -> str:
    """Strip everything that belongs to the report rather than to the source.

    Applied to EVERY quote, whether it came from a blockquote or from quotation
    marks: reports mix the two forms, and cleaning only one leaves half the
    artefacts standing. Each of these has, on its own, made a true quote look
    fabricated.
    """
    q = _BQ_PREFIX.sub("", q)
    q = _ATTRIB_LINE.sub("", q)
    q = _ATTRIB_PAREN.sub("", q)
    return q.strip().strip('"“”').strip()


_TAG_STRIP = re.compile(r"<(script|style|noscript|svg)\b.*?</\1>", re.I | re.S)
_TAGS = re.compile(r"<[^>]+>")


def html_to_text(raw: str) -> str:
    raw = _TAG_STRIP.sub(" ", raw)
    raw = _TAGS.sub(" ", raw)
    import html as _html
    return _html.unescape(raw)


# -------------------------------------------------------------------- fetch

def fetch(url: str) -> dict:
    req = urllib.request.Request(
        url, headers={"User-Agent": UA, "Accept-Encoding": "gzip, deflate"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            body = resp.read(MAX_BYTES)
            enc = (resp.headers.get("Content-Encoding") or "").lower()
            if enc == "gzip":
                body = gzip.decompress(body)
            elif enc == "deflate":
                body = zlib.decompress(body, -zlib.MAX_WBITS)
            charset = resp.headers.get_content_charset() or "utf-8"
            text = body.decode(charset, errors="replace")
            ctype = (resp.headers.get("Content-Type") or "").lower()
            if "html" in ctype or text.lstrip()[:200].lower().startswith(
                    ("<!doctype", "<html")):
                text = html_to_text(text)
            return {"status": resp.status, "text": normalize(text),
                    "error": None, "final_url": resp.url}
    except urllib.error.HTTPError as e:
        return {"status": e.code, "text": "", "error": f"HTTP {e.code}",
                "final_url": url}
    except Exception as e:  # DNS, TLS, timeout — anything that is not a reply
        return {"status": None, "text": "", "error": f"{type(e).__name__}: {e}",
                "final_url": url}


# ----------------------------------------------------------------- extraction

# file:// is accepted only so --self-test can run without a network.
# The backtick must be excluded: reports write `https://example.com/page` in
# code spans, and a captured trailing backtick turns a live page into a dead
# URL. Two measured runs hit this and worked around it by reformatting the
# report rather than the check being fixed.
_URL_RE = re.compile(r"(?:https?|file)://[^\s<>\"'`\])}]+")

# URLs that appear INSIDE configuration examples rather than as a source. A
# report about nginx quotes `proxy_pass http://127.0.0.1/;`; counting that as a
# source invents dead URLs out of text that was never a citation.
_NON_SOURCE_HOST = re.compile(
    r"^(?:https?)://(?:127\.0\.0\.1|localhost|0\.0\.0\.0|\[?::1\]?|"
    r"[^/]*\bexample\.(?:com|org|net)\b)", re.I)


def extract_urls(report: str):
    """Return [(position, url)] with trailing punctuation trimmed and
    configuration examples dropped."""
    out = []
    for m in _URL_RE.finditer(report):
        u = m.group(0).rstrip(".,;:!?)]}>”\"'")
        if _NON_SOURCE_HOST.match(u):
            continue
        # A hostname with no dot is not a source, it is an upstream name in a
        # config example such as `proxy_pass http://backend/`. Counting those
        # invents dead URLs from text that was never a citation.
        host = u.split("//", 1)[-1].split("/", 1)[0].split(":", 1)[0]
        if host and "." not in host:
            continue
        out.append((m.start(), u))
    return out


def extract_quotes(report: str):
    """Return [(position, text)] of candidate quotations.

    Two forms cover what reports actually produce: markdown blockquotes and
    passages in quotation marks inside prose. Quotes under 30 characters are
    dropped — they match by accident and would only pollute the average.

    Backtick spans do NOT count. A backtick marks an identifier or a config
    line, not a quotation: in a first pass they inflated 29 real citations into
    95 candidates, and the `proxy_pass http://127.0.0.1/;` examples in an nginx
    report entered as though they were sources.
    """
    quotes = []

    # blockquotes, consecutive lines joined into one block
    for m in re.finditer(r"(?:^[ \t]*>[^\n]*\n?)+", report, re.M):
        body = clean_quote(m.group(0))
        if len(body) >= 30:
            quotes.append((m.start(), body))

    # straight and typographic quotation marks
    for m in re.finditer(r"[\"“]([^\"“”]{30,600})[\"”]", report):
        body = clean_quote(m.group(1))
        if len(body) >= 30:
            quotes.append((m.start(), body))

    # dedupe on normalized text, keeping the first occurrence
    seen, uniq = set(), []
    for pos, q in sorted(quotes):
        k = normalize(q)
        if not k or k in seen:
            continue
        # The report's own prose in quotation marks is not a source quote;
        # measuring it against the page would fail the agent for writing in the
        # language the user asked for.
        if not looks_like_source_quote(q):
            continue
        # An unclosed quotation mark makes the regex run to the next one far
        # below and swallow whole section headers. A passage containing `## ` or
        # a `---` rule is not a quote: it is the extractor derailing.
        if re.search(r"(?m)^\s*(?:#{1,6}\s|-{3,}\s*$)", q):
            continue
        seen.add(k)
        uniq.append((pos, q))
    return uniq


_HEADER = re.compile(r"(?m)^#{1,6}\s")


def section_bounds(report: str, pos: int):
    """Start and end of the markdown section containing `pos`."""
    starts = [m.start() for m in _HEADER.finditer(report)]
    ini = 0
    for s in starts:
        if s <= pos:
            ini = s
        else:
            return ini, s
    return ini, len(report)


def candidate_urls(report: str, pos: int, urls):
    """URLs that could be a quote's source: the ones in the SAME SECTION.

    Attributing to the nearest URL in the text does not work. A common report
    opens a section with its main URL and then cites two different pages inside
    it; by proximity, the second quote inherits the first quote's URL and shows
    up as "wrong source". In the first measurement this produced 14 false
    wrong-source hits on a report whose citations were all correct.

    With no URL in the section, fall back to the nearest one, which is at least
    something.
    """
    ini, fim = section_bounds(report, pos)
    in_section = [u for p, u in urls if ini <= p < fim]
    if in_section:
        return in_section
    return [min(urls, key=lambda pu: abs(pu[0] - pos))[1]] if urls else []


# ----------------------------------------------------------------- comparison

def _windows(quote_norm: str):
    return [quote_norm[i:i + SHINGLE]
            for i in range(0, len(quote_norm) - SHINGLE + 1, STEP)]


def _positions(windows, page_norm):
    """Where each window sits in the page, preferring the occurrence that
    continues the previous one — otherwise a phrase repeated elsewhere on the
    page breaks an otherwise intact quote."""
    out, expected = [], None
    for w in windows:
        j = -1
        if expected is not None and expected >= 0:
            j = page_norm.find(w, max(0, expected - 4))
            if j >= 0 and j > expected + 4:
                j = -1                      # not the continuation
        if j < 0:
            j = page_norm.find(w)
        out.append(j)
        expected = j + STEP if j >= 0 else None
    return out


def match_detail(quote_norm: str, page_norm: str):
    """Return (ratio, contiguity).

    `ratio` is the fraction of the quote's windows present anywhere in the
    page. `contiguity` is the fraction covered by the longest run of windows
    that are also *adjacent in the page*, in order.

    Why both are needed: a quote that fuses two non-adjacent sentences — take
    "A" and "C", drop the "B" between them — still matches almost every window,
    because only the ones straddling the seam fail. On a long passage that is a
    couple of windows out of thirty, so the ratio stays above 0.8 and the
    fabrication passes. That failure mode showed up repeatedly in small-model
    output, and it was an agent running its own contiguity check that caught
    one this function had approved.

    High ratio with low contiguity is the signature: every piece is real, the
    passage is not.
    """
    if not quote_norm or not page_norm:
        return 0.0, 0.0
    if quote_norm in page_norm:
        return 1.0, 1.0
    if len(quote_norm) <= SHINGLE:
        return (1.0, 1.0) if quote_norm in page_norm else (0.0, 0.0)

    windows = _windows(quote_norm)
    if not windows:
        return 0.0, 0.0
    pos = _positions(windows, page_norm)
    ratio = sum(1 for j in pos if j >= 0) / len(windows)

    # A run must survive markup. An inline tag becomes a space in the extracted
    # text, so windows straddling it simply do not match, and the ones after it
    # sit a few characters further along than the stride predicts. Demanding an
    # exact stride called fusion on two passages that were verbatim and
    # contiguous — the same markup artefact this whole file exists to absorb.
    #
    # So a gap is forgiven when the position resumes where the skipped windows
    # would have put it, within a tolerance that grows with the gap. A real
    # fusion skips a whole sentence and lands tens to hundreds of characters
    # off, which no tolerance this size reaches.
    found = [(i, p) for i, p in enumerate(pos) if p >= 0]
    best = 0
    if found:
        run_start = found[0][0]
        for k in range(1, len(found)):
            i_prev, p_prev = found[k - 1]
            i_cur, p_cur = found[k]
            span = i_cur - i_prev
            expected = p_prev + span * STEP
            tol = max(8, 4 * span)
            if abs(p_cur - expected) <= tol:
                best = max(best, i_cur - run_start + 1)
            else:
                run_start = i_cur
        best = max(best, 1)
    contiguity = best / len(windows) if windows else 0.0
    return ratio, contiguity


def match_ratio(quote_norm: str, page_norm: str) -> float:
    """Fraction of the quote's windows found in the page. Kept for callers that
    only want the headline number; use match_detail when fusion matters."""
    return match_detail(quote_norm, page_norm)[0]


# ---------------------------------------------------------------------- main

def run(report_path: Path, out_path, fetch_fn=fetch) -> dict:
    report = report_path.read_text(encoding="utf-8", errors="replace")
    urls = extract_urls(report)
    quotes = extract_quotes(report)

    unique_urls = sorted({u for _, u in urls})
    pages = {}
    for u in unique_urls:
        pages[u] = fetch_fn(u)
        mark = pages[u]["error"] or pages[u]["status"] or "ok"
        print(f"  fetch {str(mark):>4}  {u}", file=sys.stderr)

    results = []
    for pos, q in quotes:
        cands = candidate_urls(report, pos, urls)
        qn = normalize(q)
        detail = {u: match_detail(qn, p["text"]) for u, p in pages.items()}
        scored = {u: d[0] for u, d in detail.items()}
        best_url = max(scored, key=scored.get) if scored else None
        # Best among the URLs the section itself offers: the fair test of
        # "does the source printed next to this quote support it?"
        in_section = {u: scored.get(u, 0.0) for u in cands}
        best_section = max(in_section, key=in_section.get) if in_section else None
        ratio_section = in_section.get(best_section, 0.0) if best_section else 0.0
        contig = detail.get(best_url, (0.0, 0.0))[1] if best_url else 0.0
        results.append({
            "quote": q[:300],
            "attributed_url": best_section,
            "section_url_count": len(cands),
            "ratio_on_attributed": round(ratio_section, 3),
            "best_url": best_url,
            "best_ratio": round(scored.get(best_url, 0.0), 3) if best_url else 0.0,
            "contiguity": round(contig, 3),
            # Every piece present, the passage not: the quote welds together
            # parts of the page that are not adjacent there.
            "fusion_suspected": bool(
                best_url and scored[best_url] >= 0.8 and contig < 0.6),
            # A genuinely wrong source: the quote exists on some page the
            # report cites, but on none of the ones its own section offers.
            "wrong_source": bool(
                best_url and scored[best_url] >= 0.8 and ratio_section < 0.5),
        })

    summary = {
        "report": str(report_path),
        "n_urls": len(unique_urls),
        "n_quotes": len(results),
        "urls_dead": sorted(u for u, p in pages.items()
                            if p["error"] or (p["status"] or 0) >= 400),
        "quotes_found": sum(1 for r in results if r["ratio_on_attributed"] >= 0.8),
        "quotes_partial": sum(1 for r in results
                              if 0.4 <= r["ratio_on_attributed"] < 0.8),
        "quotes_absent": sum(1 for r in results if r["ratio_on_attributed"] < 0.4),
        "fusion_suspected": sum(1 for r in results if r["fusion_suspected"]),
        "wrong_source": sum(1 for r in results if r["wrong_source"]),
        "url_status": {u: {"status": p["status"], "error": p["error"]}
                       for u, p in pages.items()},
        "citations": results,
    }
    if out_path:
        Path(out_path).write_text(
            json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    return summary


def self_test() -> int:
    """Prove all four ends before trusting any number this tool produces:

    1. a true quote wrapped across lines still scores 1.0
    2. an invented quote stays below 0.4
    3. a quote fusing two non-adjacent sentences is flagged, even though its
       ratio stays high — every piece is real, the passage is not
    4. a URL written inside a code span is still fetched, not reported dead
    """
    import tempfile
    d = Path(tempfile.mkdtemp())
    page = d / "doc.html"
    page.write_text(
        "<html><body><p>The\n  <code>--fail-with-body</code>\n  option makes\n"
        "  curl return the body\n  even on HTTP errors.</p>"
        "<p>The first sentence of the passage states the rule plainly. "
        "An intervening sentence qualifies it in a way that changes the "
        "meaning entirely. The third sentence closes the passage off.</p>"
        "</body></html>",
        encoding="utf-8")
    url = page.as_uri()
    report = d / "report.md"
    report.write_text(
        f"### 1. curl\nVerdict: holds. Source: {url}\n\n"
        "> The `--fail-with-body` option makes curl return the body even on "
        "HTTP errors.\n\n"
        "### 2. invented\n"
        f"Source: {url}\n\n"
        "> This sentence appears nowhere on that page whatsoever, truly.\n\n"
        "### 3. fused\n"
        f"Source: {url}\n\n"
        "> The first sentence of the passage states the rule plainly. "
        "The third sentence closes the passage off.\n\n"
        f"### 4. url in a code span\nSource: `{url}`\n\n"
        "> An intervening sentence qualifies it in a way that changes the "
        "meaning entirely.\n",
        encoding="utf-8")

    s = run(report, None)
    ok = True

    def find(frag):
        return next(r for r in s["citations"] if frag in r["quote"])

    real, fake = find("fail-with-body"), find("nowhere")
    fused, span = find("third sentence closes"), find("intervening sentence qualifies")

    if real["ratio_on_attributed"] != 1.0:
        print(f"FAILED (1): true quote wrapped across 5 lines scored "
              f"{real['ratio_on_attributed']}, expected 1.0"); ok = False
    if fake["ratio_on_attributed"] >= 0.4:
        print(f"FAILED (2): invented quote scored "
              f"{fake['ratio_on_attributed']}, expected < 0.4"); ok = False
    if not fused["fusion_suspected"]:
        print(f"FAILED (3): fused quote not flagged — ratio "
              f"{fused['best_ratio']}, contiguity {fused['contiguity']}"); ok = False
    if s["urls_dead"]:
        print(f"FAILED (4): URL in a code span reported dead: "
              f"{s['urls_dead']}"); ok = False
    if span["ratio_on_attributed"] < 0.9:
        print(f"FAILED (4): quote under a code-span URL scored "
              f"{span['ratio_on_attributed']}, expected >= 0.9"); ok = False

    print("self-test OK — line wrapping survives, invention fails, fusion is "
          "caught, and a URL in backticks is still fetched"
          if ok else "self-test FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("report", nargs="?", type=Path)
    ap.add_argument("-o", "--out", type=Path)
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()

    if a.self_test:
        sys.exit(self_test())
    if not a.report:
        ap.error("pass a report, or use --self-test")

    s = run(a.report, a.out)
    print(json.dumps({k: v for k, v in s.items()
                      if k not in ("citations", "url_status")},
                     indent=2, ensure_ascii=False))
