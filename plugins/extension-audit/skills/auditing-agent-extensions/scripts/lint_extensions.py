#!/usr/bin/env python3
"""Mechanical checks for agent skills, plugins and hooks.

Covers the items marked [lint] in references/checklist.md. Everything else in
that checklist needs judgment and is not attempted here.

Usage:
    lint_extensions.py PATH [PATH...]       text report; exit 1 on any error
    lint_extensions.py PATH --json          findings as a JSON array
    lint_extensions.py PATH --plugin-validate   also run `claude plugin validate --strict`
    lint_extensions.py PATH --directory     also apply the claude.ai plugin directory's
                                            submission rules (README, license, icon, size)
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
LISTING_MAX = 1536         # Claude Code cuts description + when_to_use here
# Every frontmatter key Claude Code reads (code.claude.com/docs/en/skills).
CLAUDE_CODE_KEYS = {"name", "description", "when_to_use", "argument-hint", "arguments",
                    "disable-model-invocation", "user-invocable", "allowed-tools",
                    "disallowed-tools", "model", "effort", "context", "agent", "background",
                    "hooks", "paths", "shell", "metadata", "license", "compatibility"}
# The Agent Skills spec keys: the only ones claude.ai uploads and the Skills API
# accept; any other key there is a hard error, not ignored.
PORTABLE_KEYS = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}

# claude.ai plugin directory (claude.com/docs/plugins/pre-submission-checklist).
README_MIN_WORDS = 40
REVIEW_FILE_BYTES = 256 * 1024     # a larger non-image file is held for a reviewer
REVIEW_FILE_COUNT = 512
ICON_MIN, ICON_MAX, ICON_MAX_BYTES = 512, 2048, 2 * 1024 * 1024
ICON_PATHS = (".claude-plugin/icon.png", ".claude-plugin/icon.jpg", ".claude-plugin/icon.jpeg",
              "assets/icon.png", "assets/icon.jpg", "assets/icon.jpeg")
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico"}
LAUNCHERS = {"npx", "uvx", "bunx", "pnpx"}
# Launcher options whose value names the package, and options that take some
# other value (so that value is not mistaken for the package).
PACKAGE_FLAGS = {"uvx": {"--from"}, "npx": {"-p", "--package"}, "pnpx": {"--package"},
                 "bunx": {"-p", "--package"}}
VALUE_FLAGS = {"uvx": {"-p", "--python", "--with", "--with-editable", "--with-requirements", "--index",
                       "--index-url", "--extra-index-url", "--default-index", "-f", "--find-links",
                       "-c", "--constraints", "--overrides", "--cache-dir", "--directory",
                       "--project", "--env-file"},
               "npx": {"-c", "--call", "--cache", "--registry", "-w", "--workspace", "--userconfig"},
               "pnpx": {"--dir", "-C"}, "bunx": {"--bun-version"}}
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


def unclosed_quotes(text):
    """Frontmatter keys whose quoted value never closes. A quoted scalar may
    span lines, so the closing quote is looked for until the next key."""
    m = FRONTMATTER.match(text)
    lines = m.group(1).splitlines() if m else []
    bad = []
    for i, raw in enumerate(lines):
        km = re.match(r"^([A-Za-z_][\w-]*):[ \t]+(['\"])(.*)$", raw)
        if not km:
            continue
        q, rest = km.group(2), km.group(3)
        if not _closes(q, "\n".join([rest, *_until_next_key(lines[i + 1:])])):
            bad.append(km.group(1))
    return bad


def _closes(q, text):
    """Whether a scalar opened by quote q closes in text. Inside single quotes
    '' is a literal quote; inside double quotes a backslash escapes the next
    character. Whatever follows the closing quote (a comment) is not read."""
    i = 0
    while i < len(text):
        c = text[i]
        if q == '"' and c == "\\":
            i += 2
            continue
        if c == q:
            if q == "'" and text[i + 1:i + 2] == "'":
                i += 2
                continue
            return True
        i += 1
    return False


def _until_next_key(lines):
    for l in lines:
        if re.match(r"^[A-Za-z_][\w-]*:", l):
            return
        yield l


def frontmatter_keys(text):
    m = FRONTMATTER.match(text)
    return re.findall(r"(?m)^([A-Za-z_][\w-]*):", m.group(1)) if m else []


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
    for key in unclosed_quotes(text):
        out.append(finding("error", skill_md, 1, "yaml", f"{key}: quoted value is never closed"))
    for key in frontmatter_keys(text):
        if key not in CLAUDE_CODE_KEYS:
            out.append(finding("error", skill_md, 1, "frontmatter-key",
                               f"{key!r} is not a skill field Claude Code reads; "
                               "claude.ai and the Skills API refuse the upload"))
        elif key not in PORTABLE_KEYS:
            out.append(finding("warn", skill_md, 1, "frontmatter-key",
                               f"{key!r} is Claude Code only; claude.ai uploads and the Skills API "
                               f"accept just {', '.join(sorted(PORTABLE_KEYS))}"))
    for nested in sorted(d.rglob("SKILL.md")):
        if nested != skill_md and not any(part in SKIP_DIRS for part in nested.relative_to(d).parts):
            out.append(finding("warn", nested, 1, "nested-skill",
                               f"SKILL.md inside the skill {d.name!r}; claude.ai and the Skills API "
                               "refuse the upload"))

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
    listing = len(desc) + len(fields.get("when_to_use", ""))
    if listing > LISTING_MAX:
        out.append(finding("warn", skill_md, 1, "listing-length",
                           f"description + when_to_use is {listing} chars; Claude Code cuts the "
                           f"listing at {LISTING_MAX}, so put the key use case first"))

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


def launcher_spec(cmd, args):
    """The package a launcher runs, or None when cmd is not a launcher."""
    tool = Path(cmd).name
    if tool not in LAUNCHERS:
        return None
    it = iter(args)
    for a in it:
        flag, eq, val = a.partition("=")
        if flag in PACKAGE_FLAGS[tool]:
            return val if eq else next(it, "")
        if flag in VALUE_FLAGS[tool]:
            if not eq:
                next(it, None)
            continue
        if not a.startswith("-"):
            return a
    return ""


def pinned(spec):
    """Exact version: uv's pkg==1.2.3 or npm's pkg@1.2.3 (not a range, not latest)."""
    return bool(re.search(r"==\d[\w.+-]*$", spec) or re.search(r"(?<=.)@v?\d+\.\d+\.\d+[\w.+-]*$", spec))


def _dict(v):
    return v if isinstance(v, dict) else {}


def _load_json(path):
    """A JSON object from path, or {} when it is missing, unreadable or not an object;
    `claude plugin validate` is the check that reports a malformed file."""
    try:
        return _dict(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return {}


def launchers(plugin):
    """(file, package spec) for every npx/uvx-style launcher in MCP configs and hooks."""
    found = []
    for cfg in (plugin / ".mcp.json", plugin / "mcp.json"):
        servers = _dict(_load_json(cfg).get("mcpServers"))
        for srv in map(_dict, servers.values()):
            args = srv.get("args")
            spec = launcher_spec(str(srv.get("command", "")),
                                 [str(a) for a in args] if isinstance(args, list) else [])
            if spec is not None:
                found.append((cfg, spec))
    for hooks in sorted(plugin.rglob("hooks.json")):
        if any(part in SKIP_DIRS for part in hooks.relative_to(plugin).parts):
            continue
        for groups in _dict(_load_json(hooks).get("hooks")).values():
            for group in groups if isinstance(groups, list) else []:
                for h in map(_dict, _dict(group).get("hooks") or []):
                    words = str(h.get("command", "")).split()
                    if words:
                        spec = launcher_spec(words[0], words[1:])
                        if spec is not None:
                            found.append((hooks, spec))
    return found


def image_size(path):
    """(format, width, height) from a PNG or JPEG header, or (format, None, None)."""
    b = path.read_bytes()
    if b[:8] == b"\x89PNG\r\n\x1a\n" and b[12:16] == b"IHDR":
        return "png", int.from_bytes(b[16:20], "big"), int.from_bytes(b[20:24], "big")
    if b[:2] == b"\xff\xd8":
        i = 2
        while i + 9 <= len(b):
            if b[i] != 0xFF:
                i += 1
                continue
            marker = b[i + 1]
            if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7 or marker == 0xFF:
                i += 1 if marker == 0xFF else 2
                continue
            seg = int.from_bytes(b[i + 2:i + 4], "big")
            if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
                return "jpeg", int.from_bytes(b[i + 7:i + 9], "big"), int.from_bytes(b[i + 5:i + 7], "big")
            i += 2 + seg
        return "jpeg", None, None
    if b[:4] == b"RIFF" and b[8:12] == b"WEBP":
        return "webp", None, None
    if b.lstrip()[:5] in (b"<?xml", b"<svg ") or b"<svg" in b[:512]:
        return "svg", None, None
    return "unknown", None, None


def check_directory(plugin, manifest):
    """The claude.ai plugin directory's submission rules a file walk can decide."""
    out = []
    readme = next((p for p in sorted(plugin.glob("*")) if p.name.lower() in ("readme.md", "readme")), None)
    if readme is None:
        out.append(finding("error", plugin, 0, "directory-readme", "no README; the listing uses it"))
    else:
        words = len(re.findall(r"\w+", CODE_FENCE.sub("", readme.read_text(encoding="utf-8", errors="replace"))))
        if words < README_MIN_WORDS:
            out.append(finding("error", readme, 1, "directory-readme",
                               f"{words} words outside code blocks < {README_MIN_WORDS}"))
    if not manifest.get("license") and not any(p.name.upper().startswith(("LICENSE", "LICENCE"))
                                                for p in plugin.glob("*")):
        out.append(finding("error", plugin, 0, "directory-license", "no LICENSE file and no license field"))

    icon = manifest.get("icon")
    icon_path = plugin / icon if isinstance(icon, str) else next(
        (plugin / c for c in ICON_PATHS if (plugin / c).is_file()), None)
    if icon_path is None:
        out.append(finding("error", plugin / ".claude-plugin" / "plugin.json", 0, "directory-icon",
                           "no icon: set icon in .claude-plugin/plugin.json or add .claude-plugin/icon.png"))
    elif not icon_path.is_file():
        out.append(finding("error", plugin / ".claude-plugin" / "plugin.json", 0, "directory-icon",
                           f"icon {icon} does not exist"))
    else:
        fmt, w, h = image_size(icon_path)
        size = icon_path.stat().st_size
        if fmt not in ("png", "jpeg"):
            out.append(finding("error", icon_path, 0, "directory-icon", f"{fmt} icon; use PNG or JPEG"))
        elif w is None:
            out.append(finding("warn", icon_path, 0, "directory-icon", "could not read the image size"))
        elif w != h or not ICON_MIN <= w <= ICON_MAX:
            out.append(finding("error", icon_path, 0, "directory-icon",
                               f"{w}x{h}; needs square, {ICON_MIN}-{ICON_MAX} px a side"))
        if size >= ICON_MAX_BYTES:
            out.append(finding("error", icon_path, 0, "directory-icon", f"{size} bytes; needs < 2 MB"))
        out.append(finding("warn", icon_path, 0, "directory-icon-once",
                           "the portal takes the icon only on the first save or submit"))

    files = [p for p in plugin.rglob("*") if p.is_file() and not any(x in SKIP_DIRS for x in p.relative_to(plugin).parts)]
    for p in files:
        if p.name == ".DS_Store":
            out.append(finding("error", p, 0, "directory-files", ".DS_Store blocks a submission"))
        elif p.suffix.lower() not in IMAGE_SUFFIXES and p.stat().st_size > REVIEW_FILE_BYTES:
            out.append(finding("warn", p, 0, "directory-files",
                               f"{p.stat().st_size // 1024} KiB > 256 KiB; held for a reviewer"))
    if len(files) > REVIEW_FILE_COUNT:
        out.append(finding("warn", plugin, 0, "directory-files",
                           f"{len(files)} files > {REVIEW_FILE_COUNT}; held for a reviewer"))
    if (plugin / "bin").is_dir():
        out.append(finding("warn", plugin / "bin", 0, "directory-bin",
                           "a top-level bin/ stops installation in claude.ai and Cowork"))
    return out


def check_plugin(plugin, run_validate, directory=False):
    out = []
    manifest = _load_json(plugin / ".claude-plugin" / "plugin.json")
    for cfg, spec in launchers(plugin):
        if not pinned(spec):
            out.append(finding("warn", cfg, 0, "launcher-pin",
                               f"{spec or 'a launcher'} without an exact version; the plugin directory "
                               "refuses it and every install may get a different release"))
    if directory:
        out += check_directory(plugin, manifest)
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
            cmd = [claude, "plugin", "validate", "--strict"]
            if directory:
                cmd += ["--profile", "directory"]
            r = subprocess.run(cmd + [str(plugin)],
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


def lint(paths, run_validate=False, directory=False):
    out = []
    for root in paths:
        skills, plugins = walk(Path(root))
        for s in skills:
            out += check_skill(s)
        for p in plugins:
            out += check_plugin(p, run_validate, directory)
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

        fm = t / "fm"
        fm.mkdir()
        cases = {
            "unclosed": ("description: \"Does a thing. Use when asked.\n", ("error", "yaml")),
            "unknown": ("description: Does a thing.\nfoo: bar\n", ("error", "frontmatter-key")),
            "cc-only": ("description: Does a thing.\nwhen_to_use: When asked.\n", ("warn", "frontmatter-key")),
            "listing": ("description: Does a thing.\nwhen_to_use: " + "w" * 1600 + "\n", ("warn", "listing-length")),
        }
        for case, (front, want) in cases.items():
            sk = fm / case
            sk.mkdir()
            (sk / "SKILL.md").write_text(f"---\nname: {case}\n{front}---\n# X\n", encoding="utf-8")
            if want not in {(f["level"], f["rule"]) for f in lint([sk])}:
                fails.append(f"{case}: missed {want}")
        for ok_front in ("description: 'It''s fine. Use when asked.'\n",
                         "description: \"Does a thing.\" # note\n",
                         "description: 'Does a thing.'\n# a comment\nlicense: MIT\n",
                         "description: \"Spans\n  two lines.\"\n",
                         "description: \"Has a \\\" quote.\"\n"):
            sk = fm / "quoted"
            sk.mkdir(exist_ok=True)
            (sk / "SKILL.md").write_text(f"---\nname: quoted\n{ok_front}---\n# X\n", encoding="utf-8")
            if lint([sk]):
                fails.append(f"valid quoting flagged: {ok_front!r} {lint([sk])}")
        inner = fm / "quoted" / "sub"
        inner.mkdir()
        (inner / "SKILL.md").write_text("---\nname: sub\ndescription: Inner.\n---\n", encoding="utf-8")
        if "nested-skill" not in {f["rule"] for f in lint([fm / "quoted"])}:
            fails.append("nested SKILL.md not flagged")

        for spec, want in (("kinocut==1.16.4", True), ("@scope/pkg@1.2.3", True), ("pkg@latest", False),
                           ("pkg@^1.2.0", False), ("pkg", False), ("@scope/pkg", False)):
            if pinned(spec) != want:
                fails.append(f"pinned({spec!r}) != {want}")
        if launcher_spec("uvx", ["-p", "3.12", "k==1.0"]) != "k==1.0" or \
                launcher_spec("uvx", ["--with", "e==1.0", "k"]) != "k" or \
                launcher_spec("uvx", ["--python=3.12", "k==1.0"]) != "k==1.0" or \
                launcher_spec("npx", ["--package=p@1.0.0", "cmd"]) != "p@1.0.0" or \
                launcher_spec("uvx", ["--from", "a==1.0", "kino"]) != "a==1.0" or \
                launcher_spec("npx", ["-y", "b@2.0.0"]) != "b@2.0.0" or launcher_spec("node", ["x"]) is not None:
            fails.append("launcher_spec misread a command")

        dirp = t / "dirp"
        (dirp / ".claude-plugin").mkdir(parents=True)
        (dirp / ".claude-plugin" / "plugin.json").write_text(
            '{"name": "dirp", "icon": "icon.svg"}', encoding="utf-8")
        (dirp / ".mcp.json").write_text('{"mcpServers": {"s": {"command": "npx", "args": ["-y", "srv"]}}}',
                                        encoding="utf-8")
        (dirp / "README.md").write_text("Too short.\n```\n" + "word " * 50 + "\n```\n", encoding="utf-8")
        (dirp / "icon.svg").write_text("<svg xmlns='http://www.w3.org/2000/svg'/>", encoding="utf-8")
        (dirp / ".DS_Store").write_bytes(b"x")
        (dirp / "bin").mkdir()
        (dirp / "big.json").write_bytes(b" " * (REVIEW_FILE_BYTES + 1))
        if lint([dirp]) != [f for f in lint([dirp]) if f["rule"] == "launcher-pin"] or not lint([dirp]):
            fails.append(f"without --directory, expected only launcher-pin: {lint([dirp])}")
        got = {(f["level"], f["rule"]) for f in lint([dirp], directory=True)}
        for want in [("error", "directory-readme"), ("error", "directory-license"), ("error", "directory-icon"),
                     ("error", "directory-files"), ("warn", "directory-files"), ("warn", "directory-bin"),
                     ("warn", "launcher-pin")]:
            if want not in got:
                fails.append(f"directory: missed {want}")

        broken = t / "broken"
        (broken / ".claude-plugin").mkdir(parents=True)
        (broken / ".claude-plugin" / "plugin.json").write_text("[]", encoding="utf-8")
        (broken / ".mcp.json").write_text('{"mcpServers": {"s": "x", "t": {"command": "npx", "args": null}}}',
                                          encoding="utf-8")
        (broken / "hooks").mkdir()
        (broken / "hooks" / "hooks.json").write_text('{"hooks": {"PreToolUse": ["x", {"hooks": [1]}]}}',
                                                     encoding="utf-8")
        (broken / "node_modules" / "dep").mkdir(parents=True)
        (broken / "node_modules" / "dep" / "hooks.json").write_text(
            '{"hooks": {"Stop": [{"hooks": [{"command": "npx foo"}]}]}}', encoding="utf-8")
        try:
            pins = [f for f in lint([broken], directory=True) if f["rule"] == "launcher-pin"]
            if len(pins) != 1:
                fails.append(f"malformed configs: expected the one npx in .mcp.json, got {pins}")
        except Exception as exc:  # noqa: BLE001
            fails.append(f"malformed configs crashed the linter: {exc!r}")

        png = t / "png"
        png.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + (1024).to_bytes(4, "big") * 2 + b"\x08\x06")
        jpg = t / "jpg"
        jpg.write_bytes(b"\xff\xd8\xff\xe0\x00\x10" + b"JFIF\x00" + b"\x00" * 9
                        + b"\xff\xc0\x00\x11\x08" + (300).to_bytes(2, "big") + (600).to_bytes(2, "big") + b"\x03")
        jpg_end = t / "jpg-end"
        jpg_end.write_bytes(b"\xff\xd8\xff\xc0\x00\x11\x08" + (600).to_bytes(2, "big") * 2 + b"\x03")
        if image_size(png) != ("png", 1024, 1024) or image_size(jpg) != ("jpeg", 600, 300) \
                or image_size(jpg_end) != ("jpeg", 600, 600):
            fails.append(f"image_size: {image_size(png)} {image_size(jpg)}")
        good_plug = t / "good-plug"
        (good_plug / ".claude-plugin").mkdir(parents=True)
        (good_plug / ".claude-plugin" / "plugin.json").write_text('{"name": "good-plug", "license": "MIT"}',
                                                                   encoding="utf-8")
        (good_plug / ".claude-plugin" / "icon.png").write_bytes(png.read_bytes())
        (good_plug / "README.md").write_text("word " * 45, encoding="utf-8")
        errs = [f for f in lint([good_plug], directory=True) if f["level"] == "error"]
        if errs:
            fails.append(f"clean plugin failed --directory: {errs}")

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
    ap.add_argument("--directory", action="store_true",
                    help="also apply the claude.ai plugin directory's submission rules")
    a = ap.parse_args()
    found = lint(a.paths, a.plugin_validate, a.directory)
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
