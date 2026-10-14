#!/usr/bin/env python3
"""Mechanical checks for a repo's agent-instruction files. No model, no network.

Usage: check_agents_md.py <repo-dir>   exit 1 when anything is flagged
       check_agents_md.py --self-test
"""
import json
import pathlib
import re
import sys
import tempfile

MAX_LINES, MAX_BYTES = 150, 10_000
ANTIGRAVITY_FILE_CAP = 24_000
SHOUT = re.compile(r"\b(CRITICAL|ALWAYS USE FIRST|YOU MUST|NEVER EVER)\b")
NPM_RUN = re.compile(r"\b(?:npm run|pnpm run|yarn run|bun run)\s+([a-z][\w:.-]*)")
TICKED_PATH = re.compile(r"`([\w./-]+/[\w.-]+\.[a-z]{1,6})`")
BARE_IMPORT = re.compile(r"^\s*@(?!\[)([\w./-]+)\s*$", re.M)


def check(repo: pathlib.Path) -> list[str]:
    out = []
    agents = repo / "AGENTS.md"
    for shadow in ("CLAUDE.md", ".claude/CLAUDE.md", "CLAUDE.local.md"):
        p = repo / shadow
        if agents.exists() and p.exists() and "@AGENTS.md" not in p.read_text(encoding="utf-8"):
            out.append(f"{shadow}: exists, so Claude Code skips AGENTS.md (no @AGENTS.md import)")
    gem = repo / "GEMINI.md"
    if gem.exists():
        for m in BARE_IMPORT.finditer(gem.read_text(encoding="utf-8")):
            out.append(f"GEMINI.md: '@{m.group(1)}' is not inlined by Antigravity (only @[label](path) is)")
    pkg = repo / "package.json"
    scripts = set()
    if pkg.exists():
        try:
            scripts = set(json.loads(pkg.read_text(encoding="utf-8")).get("scripts", {}))
        except ValueError:
            out.append("package.json: does not parse")
    files = [agents] + sorted((repo / "docs" / "agents").glob("*.md"))
    for f in files:
        if not f.exists():
            continue
        text = f.read_text(encoding="utf-8")
        name = f.relative_to(repo).as_posix()
        lines, size = text.count("\n") + (not text.endswith("\n") and bool(text)), len(text.encode())
        if f == agents and (lines > MAX_LINES or size > MAX_BYTES):
            out.append(f"{name}: {lines} lines / {size} bytes (cap {MAX_LINES} / {MAX_BYTES})")
        if size > ANTIGRAVITY_FILE_CAP:
            out.append(f"{name}: over {ANTIGRAVITY_FILE_CAP} bytes, Antigravity truncates it")
        for s in sorted(set(NPM_RUN.findall(text))):
            if pkg.exists() and s not in scripts:
                out.append(f"{name}: `npm run {s}` but package.json has no script '{s}'")
        for p in sorted(set(TICKED_PATH.findall(text))):
            if "<" in p or "*" in p:
                continue
            if not (repo / p).exists() and not (f.parent / p).exists():
                out.append(f"{name}: cites `{p}`, which does not exist")
        for n, line in enumerate(text.splitlines(), 1):
            if SHOUT.search(line):
                out.append(f"{name}:{n}: shouting ({SHOUT.search(line).group(1)})")
    return out


def self_test() -> int:
    with tempfile.TemporaryDirectory() as d:
        r = pathlib.Path(d)
        (r / "src").mkdir()
        (r / "src/main.ts").write_text("")
        (r / "package.json").write_text('{"scripts": {"test": "jest"}}')
        (r / "AGENTS.md").write_text("Run `npm run test`.\nSee `src/main.ts` and `src/gone.ts`.\nCRITICAL: x\n")
        (r / "CLAUDE.md").write_text("old stuff\n")
        (r / "GEMINI.md").write_text("@CLAUDE.md\n")
        got = check(r)
        want = ["CLAUDE.md: exists", "GEMINI.md: '@CLAUDE.md'", "cites `src/gone.ts`", "AGENTS.md:3: shouting"]
        miss = [w for w in want if not any(w in g for g in got)]
        bad = [g for g in got if "main.ts" in g or "npm run test" in g]
        (r / "AGENTS.md").write_text("Run `npm run build`.\n")
        (r / "CLAUDE.md").write_text("@AGENTS.md\n")
        second = check(r)
        if miss or bad or not any("'build'" in g for g in second) or any(g.startswith("CLAUDE.md") for g in second):
            print("self-test FAILED", miss, bad, got, second)
            return 1
    print("self-test ok")
    return 0


def main(argv: list[str]) -> int:
    if argv[1:] == ["--self-test"]:
        return self_test()
    if len(argv) != 2 or not pathlib.Path(argv[1]).is_dir():
        print(__doc__.strip())
        return 2
    found = check(pathlib.Path(argv[1]))
    for line in found:
        print(line)
    if not found:
        print("ok")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
