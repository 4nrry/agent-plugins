#!/usr/bin/env python3
"""Mechanical checks for agent skills, plugins and hooks.

Covers the items marked [lint] in references/checklist.md. Everything else in
that checklist needs judgment and is not attempted here.

Usage:
    lint_extensions.py PATH [PATH...]       text report; exit 1 on any error
    lint_extensions.py PATH --json          findings as a JSON array
    lint_extensions.py PATH --plugin-validate   also run `claude plugin validate --strict`
    lint_extensions.py --self-test

PATH is a repository, a plugin or a skill directory. Every SKILL.md below it is
checked, and every directory holding .claude-plugin/plugin.json is checked as
a plugin. Stdlib only.
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "worktrees"}

# Limits from the Agent Skills spec and Anthropic's authoring guide.
NAME_MAX = 64
DESCRIPTION_MAX = 1024
BODY_MAX_LINES = 500
TOC_AFTER_LINES = 100      # reference files longer than this need a table of contents
TOC_SEARCH_LINES = 30      # where to look for it

RESERVED = ("anthropic", "claude")
MARKETING = ("powerful", "comprehensive", "seamless", "cutting-edge", "state-of-the-art",
             "revolutionary", "robust", "world-class", "best-in-class", "supercharge")
# Portuguese words with no English homograph, so a hit is not an English word
# that happens to match ("no", "do" and "a" are excluded for that reason).
PT_MARKERS = {"não", "você", "também", "então", "porque", "quando", "isso", "esse", "essa",
              "está", "são", "pelo", "pela", "uma", "para", "com", "sem", "já", "só", "até",
              "onde", "cada", "ainda", "mais", "deve", "pode", "seu", "sua"}
PT_MIN_HITS, PT_MIN_RATIO = 5, 0.03   # below either, a few loanwords in English prose

FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n?", re.S)
LINK = re.compile(r"\[[^\]]*\]\(([^)\s#]+)(?:#[^)]*)?\)")
CODE_FENCE = re.compile(r"```.*?```", re.S)
INLINE_CODE = re.compile(r"`[^`\n]+`")
ISO_DATE = re.compile(r"\b20\d\d-[01]\d-[0-3]\d\b")
TESTED_VERSION = re.compile(r"\b(tested|testado)\s+(on|in|with|against|no|na|em)\s+(?:[^\s.]+\s+){0,2}[*_`]*v?\d+\.\d+", re.I)
FIRST_PERSON = re.compile(r"\b(I can|I will|I'll|I help|You can|you can use|We can)\b")
BACKSLASH_PATH = re.compile(r"\b[\w.-]+\\[\w.-]+\.(py|sh|md|json|js|ts)\b")
HAND_JSON = re.compile(r"""\b(echo|printf)\s+(-e\s+)?['"]\{""")


def finding(level, path, line, rule, msg):
    return {"level": level, "path": str(path), "line": line, "rule": rule, "message": msg}


def parse_frontmatter(text):
    """(fields, body, body_start_line) — a flat `key: value` reader; nested YAML is ignored."""
    m = FRONTMATTER.match(text)
    if not m:
        return None, text, 1
    fields, key = {}, None
    for raw in m.group(1).splitlines():
        if re.match(r"^[A-Za-z_][\w-]*:", raw):
            key, _, val = raw.partition(":")
            key = key.strip()
            fields[key] = val.strip().strip("'\"")
        elif key and raw.startswith((" ", "\t")) and fields.get(key) in ("", ">", "|", ">-", "|-"):
            fields[key + "\0cont"] = (fields.get(key + "\0cont", "") + " " + raw.strip()).strip()
    for k in [k for k in fields if k.endswith("\0cont")]:
        fields[k[:-5]] = fields.pop(k)
    return fields, text[m.end():], m.group(0).count("\n") + 1


def unsafe_scalars(text):
    """Frontmatter keys whose plain (unquoted) value strict YAML parsers reject:
    ': ' inside it, ' #' (starts a comment) or a trailing ':'. Claude Code reads
    these leniently; Copilot CLI drops the whole skill without a message."""
    m = FRONTMATTER.match(text)
    bad = []
    for raw in (m.group(1).splitlines() if m else []):
        km = re.match(r"^([A-Za-z_][\w-]*):[ \t]+(\S.*)$", raw)
        if not km:
            continue
        val = km.group(2).rstrip()
        if val[0] in "'\"[{>|&*!%@`":
            continue
        if ": " in val or " #" in val or val.endswith(":"):
            bad.append(km.group(1))
    return bad


def prose(text):
    return CODE_FENCE.sub("", text)


def blank_code(text):
    """Code replaced by spaces of the same length, so match offsets still map to lines."""
    keep = lambda m: re.sub(r"[^\n]", " ", m.group(0))  # noqa: E731
    return INLINE_CODE.sub(keep, CODE_FENCE.sub(keep, text))


def line_of(text, pos, offset=0):
    return text.count("\n", 0, pos) + 1 + offset


def is_portuguese(text):
    words = re.findall(r"[a-zà-ú]+", prose(text).lower())
    hits = sum(w in PT_MARKERS for w in words)
    return hits >= PT_MIN_HITS and words and hits / len(words) >= PT_MIN_RATIO


def check_skill(skill_md):
    out = []
    d = skill_md.parent
    text = skill_md.read_text(encoding="utf-8")
    fields, body, off = parse_frontmatter(text)
    if fields is None:
        return [finding("error", skill_md, 1, "frontmatter", "no YAML frontmatter on the first line")]

    for key in unsafe_scalars(text):
        out.append(finding("error", skill_md, 1, "yaml",
                           f"{key}: unquoted value with ': ', ' #' or a trailing ':' is invalid YAML; "
                           "quote it or reword (strict parsers such as Copilot CLI drop the skill)"))

    name = fields.get("name", "")
    if not name:
        out.append(finding("error", skill_md, 1, "name", "missing name"))
    else:
        if len(name) > NAME_MAX or not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", name):
            out.append(finding("error", skill_md, 1, "name", f"{name!r}: ≤{NAME_MAX} lowercase letters, digits, hyphens"))
        if any(r in name for r in RESERVED):
            out.append(finding("error", skill_md, 1, "name", f"{name!r} contains a reserved word"))
        if name != d.name and not (d / ".claude-plugin").is_dir():
            out.append(finding("error", skill_md, 1, "name", f"{name!r} does not match directory {d.name!r}"))

    desc = fields.get("description", "")
    if not desc:
        out.append(finding("error", skill_md, 1, "description", "missing description"))
    else:
        if len(desc) > DESCRIPTION_MAX:
            out.append(finding("error", skill_md, 1, "description", f"{len(desc)} chars > {DESCRIPTION_MAX}"))
        if re.search(r"<[A-Za-z/][^>]*>", desc):
            out.append(finding("error", skill_md, 1, "description", "contains an XML tag"))
        if FIRST_PERSON.search(desc):
            out.append(finding("warn", skill_md, 1, "description-person", "write in third person"))

    n = len(body.splitlines())
    if n > BODY_MAX_LINES:
        out.append(finding("error", skill_md, off, "body-length", f"{n} lines > {BODY_MAX_LINES}"))

    whole = desc + "\n" + body
    if is_portuguese(whole):
        out.append(finding("warn", skill_md, 1, "language", "body or description is not in English"))
    for word in MARKETING:
        m = re.search(rf"\b{re.escape(word)}\b", prose(whole), re.I)
        if m:
            out.append(finding("warn", skill_md, off, "marketing", f"marketing word {word!r}"))
    for rx, rule, msg in ((ISO_DATE, "dated", "ISO date in the body"),
                          (TESTED_VERSION, "dated", "tested-version claim in the body"),
                          (re.compile(r"\$\{CLAUDE_PLUGIN_ROOT\}"), "plugin-root",
                           "${CLAUDE_PLUGIN_ROOT} in a skill; use a path relative to the skill"),
                          (BACKSLASH_PATH, "backslash-path", "Windows-style path")):
        for m in rx.finditer(body):
            out.append(finding("warn", skill_md, line_of(body, m.start(), off - 1), rule, msg))
            break   # one per rule per file keeps the report readable

    linked_from_skill = set()
    for m in LINK.finditer(blank_code(body)):
        target = m.group(1)
        if re.match(r"^[a-z]+:", target) or target.startswith("/"):
            continue
        p = (d / target).resolve()
        if not p.exists():
            out.append(finding("error", skill_md, line_of(body, m.start(), off - 1), "link", f"broken link {target}"))
        else:
            linked_from_skill.add(p)

    for md in sorted(d.rglob("*.md")):
        if md == skill_md or any(part in SKIP_DIRS for part in md.parts):
            continue
        t = md.read_text(encoding="utf-8")
        lines = t.splitlines()
        if len(lines) > TOC_AFTER_LINES and not re.search(r"(?im)^#+\s*(contents|table of contents)\b",
                                                           "\n".join(lines[:TOC_SEARCH_LINES])):
            out.append(finding("warn", md, 1, "toc", f"{len(lines)} lines without a table of contents"))
        for m in LINK.finditer(blank_code(t)):
            target = m.group(1)
            if re.match(r"^[a-z]+:", target) or not target.endswith(".md"):
                continue
            p = (md.parent / target).resolve()
            if not p.exists():
                out.append(finding("error", md, line_of(t, m.start()), "link", f"broken link {target}"))
            elif p not in linked_from_skill and p != skill_md.resolve():
                out.append(finding("warn", md, line_of(t, m.start()), "nested-reference",
                                   f"{target} is reachable only through another reference"))
    return out


def check_plugin(plugin, run_validate):
    out = []
    if (plugin / "commands").is_dir():
        out.append(finding("warn", plugin / "commands", 0, "commands-dir", "prefer skills/ for new components"))
    for script in sorted((plugin / "hooks").glob("*")) if (plugin / "hooks").is_dir() else []:
        if script.suffix == ".json" or not script.is_file():
            continue
        t = script.read_text(encoding="utf-8", errors="replace")
        m = HAND_JSON.search(t)
        if m:
            out.append(finding("warn", script, line_of(t, m.start()), "hook-json",
                               "JSON built by echo/printf; use jq or a JSON library"))
    if run_validate:
        claude = shutil.which("claude")
        if not claude:
            out.append(finding("warn", plugin, 0, "plugin-validate", "claude not on PATH; validator skipped"))
        else:
            r = subprocess.run([claude, "plugin", "validate", "--strict", str(plugin)],
                               capture_output=True, text=True, timeout=120, stdin=subprocess.DEVNULL)
            if r.returncode != 0:
                tail = (r.stdout + r.stderr).strip().splitlines()[-3:]
                out.append(finding("error", plugin, 0, "plugin-validate", " | ".join(tail)))
    return out


def walk(root):
    root = root.resolve()
    if root.is_file():
        return [root], []
    skills, plugins = [], []
    for p in sorted(root.rglob("SKILL.md")):
        if not any(part in SKIP_DIRS for part in p.relative_to(root).parts):
            skills.append(p)
    for p in sorted(root.rglob(".claude-plugin/plugin.json")):
        if not any(part in SKIP_DIRS for part in p.relative_to(root).parts):
            plugins.append(p.parent.parent)
    return skills, plugins


def lint(paths, run_validate=False):
    out = []
    for root in paths:
        skills, plugins = walk(Path(root))
        for s in skills:
            out += check_skill(s)
        for p in plugins:
            out += check_plugin(p, run_validate)
    return out


def self_test():
    fails = []
    with tempfile.TemporaryDirectory() as tmp:
        t = Path(tmp)
        good = t / "good-skill"
        (good / "references").mkdir(parents=True)
        (good / "SKILL.md").write_text(
            "---\nname: good-skill\ndescription: Extracts tables from PDFs. Use when the user mentions PDFs.\n---\n"
            "# Good\nSee [ref](references/ref.md).\n", encoding="utf-8")
        (good / "references" / "ref.md").write_text("# Ref\nshort\n", encoding="utf-8")
        if lint([good]):
            fails.append(f"clean skill flagged: {lint([good])}")

        bad = t / "bad"
        bad.mkdir()
        (bad / "SKILL.md").write_text(
            "---\nname: Claude_Helper\ndescription: I can help. <b>x</b>\n---\n"
            "This is a powerful tool, tested on agy **1.4.2** on 2026-10-21. `[not](a-link.md)`\n"
            'Run "${CLAUDE_PLUGIN_ROOT}/scripts/x.sh" or scripts\\x.py. See [gone](missing.md).\n'
            + "line\n" * 501, encoding="utf-8")
        rules = {(f["level"], f["rule"]) for f in lint([bad])}
        for want in [("error", "name"), ("error", "description"), ("warn", "description-person"),
                     ("warn", "marketing"), ("warn", "dated"), ("warn", "plugin-root"),
                     ("warn", "backslash-path"), ("error", "link"), ("error", "body-length")]:
            if want not in rules:
                fails.append(f"missed {want}")

        colon = t / "colon-skill"
        colon.mkdir()
        (colon / "SKILL.md").write_text(
            "---\nname: colon-skill\ndescription: Does a thing. Not for others: they have their own.\n---\n# C\n",
            encoding="utf-8")
        if ("error", "yaml") not in {(f["level"], f["rule"]) for f in lint([colon])}:
            fails.append("missed unquoted ': ' in a description")
        (colon / "SKILL.md").write_text(
            "---\nname: colon-skill\ndescription: \"Does a thing. Not for others: they have their own.\"\n---\n# C\n",
            encoding="utf-8")
        if any(f["rule"] == "yaml" for f in lint([colon])):
            fails.append("flagged a quoted ': '")

        pt = t / "pt-skill"
        pt.mkdir()
        (pt / "SKILL.md").write_text(
            "---\nname: pt-skill\ndescription: Faz algo quando o usuario pede.\n---\n"
            "Isso não é para você. Também pode ser usado com uma pasta, já que cada uma está pronta.\n",
            encoding="utf-8")
        if not any(f["rule"] == "language" for f in lint([pt])):
            fails.append("Portuguese body not flagged")
        en = t / "en-skill"
        en.mkdir()
        (en / "SKILL.md").write_text(
            "---\nname: en-skill\ndescription: Does a thing. Use when asked.\n---\n"
            "Run the tool, then do the check. No para or com here beyond loanwords.\n", encoding="utf-8")
        if any(f["rule"] == "language" for f in lint([en])):
            fails.append("English body flagged as Portuguese")

        nest = t / "nest"
        (nest / "references").mkdir(parents=True)
        (nest / "SKILL.md").write_text("---\nname: nest\ndescription: Nests. Use when testing.\n---\n"
                                        "[a](references/a.md)\n", encoding="utf-8")
        (nest / "references" / "a.md").write_text("[b](b.md)\n", encoding="utf-8")
        (nest / "references" / "b.md").write_text("deep\n" + "x\n" * 120, encoding="utf-8")
        rules = {f["rule"] for f in lint([nest])}
        if "nested-reference" not in rules or "toc" not in rules:
            fails.append(f"nesting/toc not flagged: {rules}")

        plug = t / "plug"
        (plug / ".claude-plugin").mkdir(parents=True)
        (plug / ".claude-plugin" / "plugin.json").write_text('{"name": "plug"}', encoding="utf-8")
        (plug / "commands").mkdir()
        (plug / "hooks").mkdir()
        (plug / "hooks" / "h.sh").write_text("#!/bin/sh\necho '{\"a\": 1}'\n", encoding="utf-8")
        rules = {f["rule"] for f in lint([plug])}
        if not {"commands-dir", "hook-json"} <= rules:
            fails.append(f"plugin checks missed: {rules}")

    for f in fails:
        print("FAIL:", f)
    print(f"self-test: {'ok' if not fails else str(len(fails)) + ' failed'}")
    return 1 if fails else 0


def main():
    if "--self-test" in sys.argv[1:]:
        return self_test()
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("paths", nargs="+", type=Path)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--plugin-validate", action="store_true", help="also run claude plugin validate --strict")
    a = ap.parse_args()
    found = lint(a.paths, a.plugin_validate)
    if a.json:
        print(json.dumps(found, indent=2, ensure_ascii=False))
    else:
        for f in sorted(found, key=lambda f: (f["level"] != "error", f["path"], f["line"])):
            loc = f"{f['path']}:{f['line']}" if f["line"] else f["path"]
            print(f"{f['level']:5} {loc} [{f['rule']}] {f['message']}")
        errors = sum(f["level"] == "error" for f in found)
        print(f"\n{errors} error(s), {len(found) - errors} warning(s)")
    return 1 if any(f["level"] == "error" for f in found) else 0


if __name__ == "__main__":
    sys.exit(main())
