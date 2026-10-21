#!/usr/bin/env python3
"""Parser for the UI Automator accessibility tree. No device, no adb.

`adb-ui.sh` does the dirty part (talking to the device); only the logic lives
here, which is what can be tested on its own:

    adb_ui.py list       < dump.xml     label + bounds, one per line
    adb_ui.py find TEXT  < dump.xml     "X Y" center of the best matching node
    adb_ui.py --self-test               reads no stdin; exercises both above
"""
from __future__ import annotations

import re
import sys

NODE = re.compile(r"<node[^>]*>")
ATTR = {
    "text": re.compile(r'\btext="([^"]*)"'),
    "desc": re.compile(r'\bcontent-desc="([^"]*)"'),
}
BOUNDS = re.compile(r'\bbounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"')


def nodes(xml: str):
    """(label, (x1,y1,x2,y2), clickable) for each node with a label and bounds."""
    for m in NODE.finditer(xml):
        n = m.group(0)
        t = ATTR["text"].search(n)
        c = ATTR["desc"].search(n)
        b = BOUNDS.search(n)
        label = (t.group(1) if t else "") or (c.group(1) if c else "")
        if not label.strip() or not b:
            continue
        yield label, tuple(int(g) for g in b.groups()), 'clickable="true"' in n


def list_nodes(xml: str) -> list[str]:
    seen, out = set(), []
    for label, (x1, y1, x2, y2), _ in nodes(xml):
        key = (label, x1, y1, x2, y2)
        if key in seen:
            continue
        seen.add(key)
        out.append(f"{label!r:<52} [{x1},{y1}][{x2},{y2}]")
    return out


def find_center(xml: str, target: str) -> tuple[int, int] | None:
    """Center of the best node containing `target`.

    "Best" is the smallest CLICKABLE node: the same label often appears twice,
    on the container that takes the tap and on the inner TextView. Tapping the
    TextView works by accident inside the container and fails otherwise, so the
    preference is explicit.
    """
    target = target.lower()
    best = None
    for label, (x1, y1, x2, y2), clickable in nodes(xml):
        if target not in label.lower():
            continue
        key = (0 if clickable else 1, (x2 - x1) * (y2 - y1))
        if best is None or key < best[0]:
            best = (key, ((x1 + x2) // 2, (y1 + y2) // 2))
    return best[1] if best else None


FIXTURE = """<?xml version='1.0'?><hierarchy rotation="0">
<node text="" bounds="[0,0][1080,2400]" clickable="false">
 <node text="Continue" bounds="[100,900][980,1100]" clickable="true">
  <node text="Continue" bounds="[400,960][680,1040]" clickable="false" />
 </node>
 <node content-desc="Back" bounds="[10,150][110,250]" clickable="true" />
 <node text="No limit" bounds="[0,300][1080,400]" clickable="false" />
 <node text="" bounds="[0,500][1080,600]" clickable="true" />
</node></hierarchy>"""


def self_test() -> int:
    failures = []

    items = list_nodes(FIXTURE)
    # A node without a label is skipped; a label repeated at different bounds
    # appears twice, since they are different tap targets.
    if len(items) != 4:
        failures.append(f"list: expected 4 lines, got {len(items)}")
    if not any("Back" in i for i in items):
        failures.append("list: content-desc did not become a label")
    if any("[0,500]" in i for i in items):
        failures.append("list: unlabeled node leaked into the output")

    # Prefers the clickable container (100..980), not the inner TextView (400..680).
    if find_center(FIXTURE, "continue") != (540, 1000):
        failures.append(f"find: picked the wrong node, got {find_center(FIXTURE, 'continue')}")
    # Matches by content-desc, case-insensitively.
    if find_center(FIXTURE, "BACK") != (60, 200):
        failures.append(f"find: content-desc/case, got {find_center(FIXTURE, 'BACK')}")
    # Substring matches.
    if find_center(FIXTURE, "limit") != (540, 350):
        failures.append(f"find: substring, got {find_center(FIXTURE, 'limit')}")
    # A missing label returns None, not a guess.
    if find_center(FIXTURE, "not on screen") is not None:
        failures.append("find: returned something for a missing label")
    # An empty dump (the GL surface case) must not raise.
    if find_center("", "anything") is not None or list_nodes("") != []:
        failures.append("empty dump should return nothing, without an exception")

    for f in failures:
        print(f)
    print("self-test: ok" if not failures else f"self-test: {len(failures)} failure(s)")
    return 1 if failures else 0


def main() -> int:
    if "--self-test" in sys.argv:
        return self_test()
    if len(sys.argv) < 2:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    xml = sys.stdin.read()
    if sys.argv[1] == "list":
        for line in list_nodes(xml):
            print(line)
        return 0
    if sys.argv[1] == "find" and len(sys.argv) > 2:
        p = find_center(xml, sys.argv[2])
        if p is None:
            return 1
        print(p[0], p[1])
        return 0
    print(__doc__.strip(), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
