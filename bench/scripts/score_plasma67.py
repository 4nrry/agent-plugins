#!/usr/bin/env python3
"""Score one arm-run of the plasma67-citations eval into an outcomes object.

Reads the preserved task output (findings per eval item), verifies every
quote directly against its attributed URL using the plugin's own
verify_citations module (normalize + match_detail — no report-parsing layer,
so structured-page cell strings are measured too, which the report parser's
English-prose filter would skip), and scores the eval's four assertions.

Emits an outcomes JSON to stdout; the caller merges it into the run record.
Pages are fetched once per URL per invocation and cached in-process.
"""

import contextlib
import json
import sys
from pathlib import Path

PLUGIN_SCRIPTS = Path(sys.argv[3]) if len(sys.argv) > 3 else Path(
    "/home/anrry/.claude/plugins/cache/4nrry/agent-fleet/1.0.2/scripts")
sys.path.insert(0, str(PLUGIN_SCRIPTS))
import verify_citations as vc  # noqa: E402


def main():
    with contextlib.redirect_stdout(sys.stderr):
        outcomes = _score(Path(sys.argv[1]), Path(sys.argv[2]))
    print(json.dumps(outcomes, indent=2, ensure_ascii=False))


def _score(eval_path, task_output_path):
    ev = json.loads(eval_path.read_text(encoding="utf-8"))
    items = {i["id"]: i for i in ev["items"]}
    result = json.loads(task_output_path.read_text(encoding="utf-8"))["result"]

    pages = {}

    def page_norm(url):
        # vc.fetch returns {status, text, error, final_url}; text is already
        # normalized by fetch itself — do not normalize twice.
        if url not in pages:
            f = vc.fetch(url)
            ok = f.get("status") is not None and 200 <= f["status"] < 300 and f["text"]
            pages[url] = f["text"] if ok else None
        return pages[url]

    per_item = {}
    measured = found = partial = absent = unfetchable = 0
    wrong_source_count = 0
    all_urls = [f["url"] for q in result["perQuestion"] if q["result"]
                for f in q["result"]["findings"]]

    for q in result["perQuestion"]:
        item = items[q["key"]]
        r = q["result"]
        if r is None:
            per_item[q["key"]] = {"schema_ok": False, "key_fact": False,
                                  "findings": 0, "found": 0}
            continue
        item_found = 0
        key_fact = False
        ratios = []
        for f in r["findings"]:
            pn = page_norm(f["url"])
            qn = vc.normalize(vc.clean_quote(f["quote"]))
            if pn is None:
                unfetchable += 1
                ratios.append(None)
                continue
            measured += 1
            ratio, _contig = vc.match_detail(qn, pn)
            ratios.append(ratio)
            if ratio >= 0.8:
                found += 1
                item_found += 1
            elif ratio >= 0.5:
                partial += 1
            else:
                absent += 1
                # wrong-source: absent on the attributed page but present
                # verbatim on some other page this run cited
                for other in set(all_urls) - {f["url"]}:
                    on = page_norm(other)
                    if on and vc.match_detail(qn, on)[0] >= 0.8:
                        wrong_source_count += 1
                        break
            import re as _re
            hay = f["claim"] + " " + f["quote"]
            if ratio >= 0.8 and all(_re.search(rx, hay) for rx in item["key_fact_regexes"]):
                key_fact = True
        per_item[q["key"]] = {"schema_ok": True, "key_fact": key_fact,
                              "findings": len(r["findings"]), "found": item_found}

    self_test_ok = vc.self_test() == 0
    outcomes = {
        "verifier_self_test": self_test_ok,
        "citations": {
            "source": "script",
            "measured": measured, "found": found, "partial": partial,
            "absent": absent, "unfetchable_quotes": unfetchable,
            "found_rate": round(found / measured, 3) if measured else None,
            "wrong_source": wrong_source_count,
        },
        "assertions": {
            "source": "script",
            "schema_ok": sum(1 for v in per_item.values() if v["schema_ok"]),
            "schema_total": len(per_item),
            "key_fact_score": sum(1 for v in per_item.values() if v["key_fact"]),
            "key_fact_total": len(per_item),
            "per_item": per_item,
        },
    }
    return outcomes


if __name__ == "__main__":
    main()
