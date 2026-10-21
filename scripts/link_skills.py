#!/usr/bin/env python3
"""Link this marketplace's skills into the folders other agent tools scan.

Claude Code loads these plugins from the marketplace. Every other tool reads
plain skill folders, so each skill gets one symlink there, pointing at the
marketplace clone: `claude plugin marketplace update 4nrry` then updates every
tool at once, and nothing is copied that could go stale.

  link_skills.py global                  GLOBAL plugins -> every USER_ROOTS folder
  link_skills.py project DIR PLUGIN...   exactly these plugins -> DIR/.agents/skills,
                                         listed in .git/info/exclude when DIR is a repo
  link_skills.py status [REPO...]

Both commands are declarative: links this script made that are no longer
wanted are removed. A real file or a link made by something else is never
touched; it is reported as a conflict.
"""
import argparse
import contextlib
import io
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

GLOBAL = ["agent-fleet", "agents-md", "extension-audit", "game-facts", "homelab"]

HOME = Path.home()
# ~/.agents/skills: Grok, Cursor, Kimi Code, ZCode, opencode, and Hermes through
# skills.external_dirs. Antigravity reads none of those, only its own folder.
# Claude Code reads neither and gets the plugins instead.
USER_ROOTS = [HOME / ".agents/skills", HOME / ".gemini/config/skills"]
MARKETPLACE_CLONE = HOME / ".claude/plugins/marketplaces/4nrry"
REPO = Path(__file__).resolve().parent.parent
EXCLUDE_BEGIN = "# >>> link_skills.py (agent-plugins)"
EXCLUDE_END = "# <<< link_skills.py"


def skill_name(skill_md: Path) -> str:
    text = skill_md.read_text(encoding="utf-8")
    m = re.match(r"---\n(.*?)\n---", text, re.S)
    name = m and re.search(r"^name:\s*(\S+)\s*$", m.group(1), re.M)
    if not name:
        sys.exit(f"error: no name in the frontmatter of {skill_md}")
    return name.group(1)


def plugin_skills(source: Path, plugin: str) -> dict:
    """{skill name: skill dir} for one plugin; a SKILL.md at the root is one skill."""
    root = source / "plugins" / plugin
    if not root.is_dir():
        sys.exit(f"error: no plugin {plugin!r} in {source}/plugins")
    found = sorted([root / "SKILL.md"] if (root / "SKILL.md").is_file()
                   else root.glob("skills/*/SKILL.md"))
    return {skill_name(f): f.parent for f in found}


def wanted(source: Path, plugins: list) -> dict:
    out, owner = {}, {}
    for plugin in plugins:
        for name, path in plugin_skills(source, plugin).items():
            if name in out:
                sys.exit(f"error: skill {name!r} is in both {owner[name]} and {plugin}")
            out[name], owner[name] = path, plugin
    return out


def ours(link: Path, sources: list) -> bool:
    if not link.is_symlink():
        return False
    target = os.readlink(link)
    return any(target.startswith(f"{s}/plugins/") for s in sources)


def sync(root: Path, want: dict, sources: list, dry: bool) -> list:
    """Make root's links match want. Returns the conflicts."""
    conflicts, log = [], []
    if not dry:
        root.mkdir(parents=True, exist_ok=True)
    present = sorted(root.iterdir()) if root.is_dir() else []
    for entry in present:
        if ours(entry, sources) and entry.name not in want:
            log.append(f"  - {entry.name}")
            if not dry:
                entry.unlink()
    for name, target in sorted(want.items()):
        link = root / name
        if link.is_symlink() and ours(link, sources):
            if os.readlink(link) == str(target):
                continue
            if not dry:
                link.unlink()
        elif link.exists() or link.is_symlink():
            conflicts.append(f"{link} exists and is not this script's link")
            continue
        log.append(f"  + {name} -> {target}")
        if not dry:
            link.symlink_to(target, target_is_directory=True)
    print(f"{root}: {len(want)} wanted" + ("" if log else ", up to date"))
    for line in log:
        print(line)
    return conflicts


def git_exclude(repo: Path) -> Path:
    out = subprocess.run(["git", "-C", str(repo), "rev-parse", "--git-path", "info/exclude"],
                         capture_output=True, text=True, check=True).stdout.strip()
    path = Path(out)
    return path if path.is_absolute() else repo / path


def write_exclude(repo: Path, names: list, dry: bool) -> None:
    path = git_exclude(repo)
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    text = re.sub(rf"\n?{re.escape(EXCLUDE_BEGIN)}\n.*?{re.escape(EXCLUDE_END)}\n", "\n",
                  text, flags=re.S).rstrip("\n")
    if names:
        block = "\n".join([EXCLUDE_BEGIN, *[f"/.agents/skills/{n}" for n in names],
                           EXCLUDE_END])
        text = f"{text}\n\n{block}" if text else block
    if not dry:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text + "\n", encoding="utf-8")


def cmd_global(source, sources, roots, plugins, dry) -> int:
    want = wanted(source, plugins)
    conflicts = [c for root in roots for c in sync(root, want, sources, dry)]
    for c in conflicts:
        print(f"conflict: {c}", file=sys.stderr)
    return 1 if conflicts else 0


def cmd_project(source, sources, repo: Path, plugins, dry) -> int:
    if not repo.is_dir():
        sys.exit(f"error: no directory {repo}")
    want = wanted(source, plugins)
    conflicts = sync(repo / ".agents/skills", want, sources, dry)
    if (repo / ".git").exists():
        write_exclude(repo, sorted(want), dry)
    else:
        print(f"{repo}: not a git checkout, nothing to exclude")
    for c in conflicts:
        print(f"conflict: {c}", file=sys.stderr)
    return 1 if conflicts else 0


def cmd_status(sources, roots) -> int:
    for root in roots:
        print(root)
        for entry in sorted(root.iterdir()) if root.is_dir() else []:
            if entry.is_symlink() and ours(entry, sources):
                state = "" if entry.exists() else "  DANGLING"
                print(f"  {entry.name} -> {os.readlink(entry)}{state}")
    return 0


def mute(fn, *args):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return fn(*args)


def self_test() -> int:
    global GLOBAL
    with tempfile.TemporaryDirectory() as tmp:
        t = Path(tmp)
        src = t / "src"
        for rel, name in [("plugins/a/SKILL.md", "a"), ("plugins/b/skills/x/SKILL.md", "x"),
                          ("plugins/b/skills/y/SKILL.md", "y"), ("plugins/c/skills/z/SKILL.md", "z")]:
            (src / rel).parent.mkdir(parents=True, exist_ok=True)
            (src / rel).write_text(f"---\nname: {name}\ndescription: d\n---\nbody\n")
        roots = [t / "home/.agents/skills", t / "home/.gemini/config/skills"]
        sources = [str(src)]
        roots[0].mkdir(parents=True)
        (roots[0] / "foreign").mkdir()
        (roots[0] / "x").write_text("a real file")
        checks = 0

        def ok(cond, what):
            nonlocal checks
            checks += 1
            if not cond:
                sys.exit(f"self-test failed: {what}")

        rc = mute(cmd_global, src, sources, roots, ["a", "b"], False)
        ok(rc == 1, "a real file in the way is a conflict")
        ok((roots[0] / "x").read_text() == "a real file", "a real file is never replaced")
        ok(os.readlink(roots[1] / "x") == str(src / "plugins/b/skills/x"), "skill links to its dir")
        ok(os.readlink(roots[0] / "a") == str(src / "plugins/a"), "root SKILL.md links the plugin")
        (roots[0] / "x").unlink()
        ok(mute(cmd_global, src, sources, roots, ["a", "b"], False) == 0, "second run is clean")
        ok(mute(cmd_global, src, sources, roots, ["a"], False) == 0, "narrowing works")
        ok(not (roots[0] / "y").exists() and (roots[0] / "foreign").is_dir(),
           "only this script's links are pruned")
        mute(cmd_global, src, sources, roots, ["a"], True)
        ok(sorted(p.name for p in roots[1].iterdir()) == ["a"], "idempotent")

        repo = t / "repo"
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        excl = git_exclude(repo)
        excl.write_text("*.log\n")
        ok(mute(cmd_project, src, sources, repo, ["b", "c"], False) == 0, "project link")
        mute(cmd_project, src, sources, repo, ["b", "c"], False)
        text = excl.read_text()
        ok(text.count(EXCLUDE_BEGIN) == 1 and "/.agents/skills/z" in text and "*.log" in text,
           "exclude block written once, user lines kept")
        status = subprocess.run(["git", "-C", str(repo), "status", "--porcelain"],
                                capture_output=True, text=True, check=True).stdout
        ok(status == "", "linked skills are invisible to git")
        mute(cmd_project, src, sources, repo, [], False)
        ok(EXCLUDE_BEGIN not in excl.read_text() and excl.read_text() == "*.log\n",
           "empty set removes links and block")
        ok(not any((repo / ".agents/skills").iterdir()), "empty set prunes links")
        plain = t / "plain"
        plain.mkdir()
        ok(mute(cmd_project, src, sources, plain, ["c"], False) == 0
           and (plain / ".agents/skills/z").is_symlink(), "a folder without git still gets links")
        (src / "plugins/c/skills/x").mkdir()
        (src / "plugins/c/skills/x/SKILL.md").write_text("---\nname: x\n---\n")
        try:
            wanted(src, ["b", "c"])
            ok(False, "duplicate skill names across plugins are refused")
        except SystemExit:
            checks += 1
    print(f"self-test: {checks} checks ok")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--source", type=Path,
                    help=f"marketplace checkout to link to (default: {MARKETPLACE_CLONE} "
                         "if present, else this repo)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("global")
    p = sub.add_parser("project")
    p.add_argument("repo", type=Path)
    p.add_argument("plugins", nargs="*", help="no plugin removes the repo's links")
    s = sub.add_parser("status")
    s.add_argument("repos", nargs="*", type=Path)
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    source = (args.source or (MARKETPLACE_CLONE if MARKETPLACE_CLONE.is_dir() else REPO)).resolve()
    sources = sorted({str(source), str(MARKETPLACE_CLONE), str(REPO)})
    if args.cmd == "global":
        return cmd_global(source, sources, USER_ROOTS, GLOBAL, args.dry_run)
    if args.cmd == "project":
        return cmd_project(source, sources, args.repo.resolve(), args.plugins, args.dry_run)
    if args.cmd == "status":
        return cmd_status(sources, USER_ROOTS + [r.resolve() / ".agents/skills" for r in args.repos])
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
