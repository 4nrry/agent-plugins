#!/usr/bin/env python3
"""Turn a plugin on for one project in every agent tool that has a project scope.

`link_skills.py project DIR PLUGIN...` calls this after linking the skills into
DIR/.agents/skills (which Codex, Copilot, Cursor, Grok, opencode and Hermes read).
The rest of a plugin, its MCP servers and hooks, goes where each tool reads a
project's own config:

  Claude Code  .claude/settings.local.json  enabledPlugins["<plugin>@4nrry"]
  Codex        .codex/config.toml           [mcp_servers.<server>] and [[hooks.<event>]], as for Grok
                                            (skipped when the file is tracked). Not the plugin: Codex
                                            lists its skills beside the same .agents/skills links,
                                            twice, and honours skills.config only in the user file
  Grok         .grok/config.toml            [mcp_servers.<server>]        (via adapters/mcp_launch.py)
               .grok/hooks/4nrry-<plugin>.json                            (via adapters/claude_hooks.py)
  Antigravity  .agents/plugins/<plugin>/    plugin.json, mcp_config.json and a copy of the
                                            skills: it skips symlinks that leave the repo
  opencode, Hermes: the bridges read the .agents/skills links, nothing to write.

Declarative like the links: entries for plugins this script managed and no
longer wants are removed; entries written by hand are left alone. Config blocks
sit between marker comments; files and folders this script owns carry the
plugin name and a marker. Stdlib only.
"""
import hashlib
import json
import re
import shlex
import shutil
import subprocess
from pathlib import Path

MARKETPLACE_NAME = "4nrry"
BEGIN = "# >>> link_skills.py (agent-plugins)"
END = "# <<< link_skills.py"
OWNED = ".link_skills"  # marker file inside a folder this script owns


def git_root(path: Path):
    """The work tree root holding path, or None outside git."""
    p = subprocess.run(["git", "-C", str(path), "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    return Path(p.stdout.strip()).resolve() if p.returncode == 0 and p.stdout.strip() else None


def tracked(repo: Path, rel: str) -> bool:
    if git_root(repo) is None:
        return False
    return subprocess.run(["git", "-C", str(repo), "ls-files", "--error-unmatch", "--", rel],
                          capture_output=True).returncode == 0


def split_block(text: str):
    """(text without the managed block, block body) or None when the markers are broken."""
    lines = text.split("\n")
    begins = [i for i, line in enumerate(lines) if line == BEGIN]
    ends = [i for i, line in enumerate(lines) if line == END]
    if not begins and not ends:
        return text, ""
    if len(begins) != 1 or len(ends) != 1 or ends[0] < begins[0]:
        return None
    i, j = begins[0], ends[0]
    rest = lines[:i] + lines[j + 1:]
    while i and rest[i - 1:i] == [""]:  # the blank line this script put before the block
        del rest[i - 1]
        i -= 1
    return "\n".join(rest), "\n".join(lines[i + 1:j])


def toml_block(path: Path, body: str, dry: bool, log: list, tool: str):
    """Make the managed block of a TOML file hold body (empty removes it).
    Returns "only" when the file holds nothing but the block, "shared" when it
    also has hand-written content, None when the file has no block."""
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    parts = split_block(text)
    if parts is None:
        log.append(f"  ! {tool}: {path} has a broken {BEGIN!r} marker pair; left alone")
        return None
    rest, _ = parts
    if body:
        sep = "" if not rest.strip() else ("\n" if rest.endswith("\n") else "\n\n")
        new = (rest.lstrip("\n") if rest.strip() else "") + sep + f"{BEGIN}\n{body.strip()}\n{END}\n"
    else:
        new = rest
    if new != text and not parses(new) and parses(text):
        log.append(f"  ! {tool}: the new block would not parse beside {path}'s own tables; left alone")
        return None
    if new != text:
        log.append(f"  {tool}: {path.name}" + ("" if body else " (block removed)"))
        if not dry:
            if new.strip():
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(new, encoding="utf-8")
            elif path.exists():
                path.unlink()
    if not body:
        return None
    return "shared" if rest.strip() else "only"


def parses(text: str) -> bool:
    try:
        import tomllib
    except ImportError:  # Python < 3.11: no check
        return True
    try:
        tomllib.loads(text)
    except ValueError:
        return False
    return True


def hand_written_headers(path: Path) -> set:
    """Table paths defined outside the managed block, as tuples of keys.
    Read with tomllib when the rest parses (comments, quoted dotted keys),
    else line by line."""
    if not path.exists():
        return set()
    text = path.read_text(encoding="utf-8")
    parts = split_block(text)
    rest = parts[0] if parts else text
    try:
        import tomllib
        data = tomllib.loads(rest)
    except (ImportError, ValueError):
        data = None
    out = set()
    if data is not None:
        def walk(node, prefix):
            for k, v in node.items():
                if isinstance(v, dict):
                    out.add(prefix + (k,))
                    walk(v, prefix + (k,))
        walk(data, ())
        return out
    for line in rest.split("\n"):
        s = line.split("#", 1)[0].strip()
        if s.startswith("[") and not s.startswith("[[") and s.endswith("]"):
            out.add(tuple(x.strip().strip('"') for x in s[1:-1].split(".")))
    return out


def q(s: str) -> str:
    """A TOML basic string. ensure_ascii=False: a surrogate-pair escape is not valid TOML."""
    return json.dumps(s, ensure_ascii=False)


def mcp_servers(plugin_dir: Path) -> dict:
    try:
        servers = json.loads((plugin_dir / "mcp.json").read_text(encoding="utf-8")).get("mcpServers", {})
    except (OSError, ValueError, AttributeError):
        return {}
    return servers if isinstance(servers, dict) else {}


def hook_events(plugin_dir: Path) -> list:
    try:
        spec = json.loads((plugin_dir / "hooks" / "hooks.json").read_text(encoding="utf-8"))
        events = spec.get("hooks", {})
    except (OSError, ValueError, AttributeError):
        return []
    return sorted(e for e in events if e in ("PreToolUse", "PostToolUse", "UserPromptSubmit"))


def claude(repo: Path, plugins: list, gone: list, dry: bool, log: list) -> list:
    """Returns the file to git-exclude: it is personal, like Claude Code's own default."""
    rel = ".claude/settings.local.json"
    path = repo / rel
    excludes = [] if tracked(repo, rel) else [rel]
    try:
        data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except ValueError:
        data = None
    if not isinstance(data, dict) or not isinstance(data.get("enabledPlugins", {}), dict):
        log.append(f"  ! claude: {path} is not a settings object with an enabledPlugins map; left alone")
        return excludes
    enabled = dict(data.get("enabledPlugins", {}))
    before = dict(enabled)
    for p in plugins:
        enabled[f"{p}@{MARKETPLACE_NAME}"] = True
    for p in gone:
        enabled.pop(f"{p}@{MARKETPLACE_NAME}", None)
    if enabled != before:
        if enabled:
            data["enabledPlugins"] = enabled
        else:
            data.pop("enabledPlugins", None)
        log.append("  claude: .claude/settings.local.json" + ("" if data else " (removed, now empty)"))
        if not dry:
            if data:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
            elif path.exists():
                path.unlink()
    return excludes if data else []


def mcp_tables(source: Path, plugins: list, have: set, tool: str, rel: str, log: list) -> list:
    """[mcp_servers.<server>] tables that start each plugin's servers through adapters/mcp_launch.py."""
    launch = source / "adapters/mcp_launch.py"
    body, seen = [], {}
    for p in plugins:
        for server in sorted(mcp_servers(source / "plugins" / p)):
            if ("mcp_servers", server) in have:
                log.append(f"  ! {tool}: {rel} already has [mcp_servers.{server}] by hand; kept as is")
                continue
            if server in seen:
                log.append(f"  ! {tool}: MCP server {server!r} is in both {seen[server]} and {p}; kept {seen[server]}'s")
                continue
            seen[server] = p
            body.append(f"[mcp_servers.{q(server)}]\ncommand = \"python3\"\n"
                        f"args = [{q(str(launch))}, {q(p)}, {q(server)}]")
    return body


def codex(repo: Path, source: Path, plugins: list, dry: bool, log: list) -> list:
    """Skills come from the .agents/skills links; this adds the MCP servers and,
    inline, the hooks (Codex reads a project's [hooks] once the folder is trusted
    and each hook is reviewed)."""
    rel = ".codex/config.toml"
    path = repo / rel
    if tracked(repo, rel):
        if plugins:
            log.append(f"  ! codex: {rel} is tracked by git; not changed (Codex gets the skills only)")
        return []
    have = hand_written_headers(path)
    body = mcp_tables(source, plugins, have, "codex", rel, log)
    hooks_py = source / "adapters/claude_hooks.py"
    for p in plugins:
        for e in hook_events(source / "plugins" / p):
            cmd = " ".join(shlex.quote(a) for a in ["python3", str(hooks_py), e, "--plugin", p, "--json"])
            body.append(f"[[hooks.{e}]]\n\n[[hooks.{e}.hooks]]\ntype = \"command\"\ncommand = {q(cmd)}")
    state = toml_block(path, "\n\n".join(body), dry, log, "codex")
    return [rel] if state == "only" else []


def grok(repo: Path, source: Path, plugins: list, gone: list, dry: bool, log: list) -> list:
    rel = ".grok/config.toml"
    hooks_py = source / "adapters/claude_hooks.py"
    excludes = []
    body = mcp_tables(source, plugins, hand_written_headers(repo / rel), "grok", rel, log)
    for p in plugins:
        pdir = source / "plugins" / p
        events = hook_events(pdir)
        hook_file = repo / f".grok/hooks/4nrry-{p}.json"
        if events:
            spec = {"hooks": {e: [{"hooks": [{"type": "command", "command": "python3",
                                               "args": [str(hooks_py), e, "--plugin", p, "--json"]}]}]
                              for e in events}}
            new = json.dumps(spec, indent=2) + "\n"
            if not hook_file.exists() or hook_file.read_text(encoding="utf-8") != new:
                log.append(f"  grok: .grok/hooks/{hook_file.name}")
                if not dry:
                    hook_file.parent.mkdir(parents=True, exist_ok=True)
                    hook_file.write_text(new, encoding="utf-8")
            excludes.append(f".grok/hooks/4nrry-{p}.json")
    for p in gone:
        hook_file = repo / f".grok/hooks/4nrry-{p}.json"
        if hook_file.exists():
            log.append(f"  grok: - .grok/hooks/{hook_file.name}")
            if not dry:
                hook_file.unlink()
    if tracked(repo, rel):
        if body:
            log.append(f"  ! grok: {rel} is tracked by git; MCP servers not added")
    elif toml_block(repo / rel, "\n\n".join(body), dry, log, "grok") == "only":
        excludes.append(rel)
    return excludes


def tree_digest(folder: Path) -> str:
    h = hashlib.sha256()
    for f in sorted(folder.rglob("*")):
        if f.is_file():
            h.update(str(f.relative_to(folder)).encode() + b"\0" + f.read_bytes() + b"\0")
    return h.hexdigest()


def antigravity(repo: Path, source: Path, skills_of, plugins: list, gone: list, dry: bool, log: list) -> list:
    launch = source / "adapters/mcp_launch.py"
    excludes = []
    for p in gone:
        folder = repo / f".agents/plugins/{p}"
        if (folder / OWNED).exists():
            log.append(f"  antigravity: - .agents/plugins/{p}")
            if not dry:
                shutil.rmtree(folder)
    for p in plugins:
        pdir = source / "plugins" / p
        folder = repo / f".agents/plugins/{p}"
        if folder.exists() and not (folder / OWNED).exists():
            log.append(f"  ! antigravity: .agents/plugins/{p} exists and is not this script's; left alone")
            continue
        excludes.append(f".agents/plugins/{p}/")
        try:
            manifest = json.loads((pdir / "plugin.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            manifest = {}
        if not isinstance(manifest, dict):
            manifest = {}
        files = {"plugin.json": {"name": p, **{k: manifest[k] for k in ("version", "description") if k in manifest}}}
        servers = {s: {"command": "python3", "args": [str(launch), p, s]} for s in sorted(mcp_servers(pdir))}
        if servers:
            files["mcp_config.json"] = {"mcpServers": servers}
        skills = skills_of(p)
        try:
            stamp = json.dumps({"files": files, "skills": {n: tree_digest(d) for n, d in sorted(skills.items())}},
                               sort_keys=True)
        except OSError as exc:
            log.append(f"  ! antigravity: cannot read the skills of {p}: {exc}")
            continue
        marker = folder / OWNED
        if marker.exists() and marker.read_text(encoding="utf-8") == stamp:
            continue
        log.append(f"  antigravity: .agents/plugins/{p} ({len(skills)} skills copied)")
        if dry:
            continue
        tmp = folder.with_name(f".{p}.link_skills-tmp")
        try:
            if tmp.exists():
                shutil.rmtree(tmp)
            (tmp / "skills").mkdir(parents=True)
            for name, target in sorted(skills.items()):
                shutil.copytree(target, tmp / "skills" / name, symlinks=False)
            for name, value in files.items():
                (tmp / name).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
            (tmp / OWNED).write_text(stamp, encoding="utf-8")
        except (OSError, shutil.Error) as exc:
            shutil.rmtree(tmp, ignore_errors=True)
            log.append(f"  ! antigravity: copying the skills of {p} failed ({exc}); the old copy stays")
            continue
        if folder.exists():
            shutil.rmtree(folder)
        tmp.rename(folder)
    return excludes


def sync_tools(repo: Path, source: Path, skills_of, plugins: list, previous: list, dry: bool) -> list:
    """Write every tool's project config for plugins; remove it for previous - plugins.
    skills_of(plugin) -> {skill name: skill dir}. Returns paths relative to repo to git-exclude."""
    gone = sorted(set(previous) - set(plugins))
    log = []
    excludes = claude(repo, plugins, gone, dry, log)
    excludes += codex(repo, source, plugins, dry, log)
    excludes += grok(repo, source, plugins, gone, dry, log)
    excludes += antigravity(repo, source, skills_of, plugins, gone, dry, log)
    for line in log:
        print(line)
    return excludes


def trust_notes(repo: Path) -> list:
    """Tools that ignore this folder's config until it is trusted."""
    notes = []
    try:
        import tomllib
    except ImportError:  # Python < 3.11
        return notes
    home = Path.home()
    try:
        user = tomllib.loads((home / ".codex/config.toml").read_text(encoding="utf-8"))
        if user.get("projects", {}).get(str(repo), {}).get("trust_level") != "trusted":
            notes.append("Codex: not trusted, so .codex/config.toml is ignored "
                         f"(add [projects.\"{repo}\"] trust_level = \"trusted\" to ~/.codex/config.toml)")
        project = tomllib.loads((repo / ".codex/config.toml").read_text(encoding="utf-8"))
        state = user.get("hooks", {}).get("state", {})
        snake = lambda e: re.sub(r"(?<!^)(?=[A-Z])", "_", e).lower()  # noqa: E731
        keys = [f"{repo / '.codex/config.toml'}:{snake(e)}:{i}:{j}"
                for e, groups in (project.get("hooks") or {}).items() if e != "state" and isinstance(groups, list)
                for i, g in enumerate(groups) for j, _ in enumerate(g.get("hooks", []))]
        if any("trusted_hash" not in state.get(k, {}) for k in keys):
            notes.append("Codex: the project hooks run only once reviewed (open Codex there and trust them in /hooks)")
    except (OSError, ValueError):
        pass
    try:
        folders = tomllib.loads((home / ".grok/trusted_folders.toml").read_text(encoding="utf-8")).get("folders", {})
        if not any(folders.get(str(p), {}).get("trusted") for p in (repo, *repo.parents)):
            notes.append("Grok: not trusted, so .grok/ and .agents/skills are ignored (run /hooks-trust there)")
    except (OSError, ValueError):
        pass
    return notes


def self_test() -> int:
    import sys
    import tempfile
    import tomllib
    with tempfile.TemporaryDirectory() as tmp:
        t = Path(tmp)
        src, repo = t / "src", t / "repo"
        pdir = src / "plugins/m"
        (pdir / "skills/s1").mkdir(parents=True)
        (pdir / "skills/s1/SKILL.md").write_text("---\nname: s1\ndescription: d\n---\n")
        (pdir / "hooks").mkdir()
        (pdir / "plugin.json").write_text('{"name": "m", "version": "1.0", "description": "d"}')
        (pdir / "mcp.json").write_text('{"mcpServers": {"srv": {"command": "x"}}}')
        (pdir / "hooks/hooks.json").write_text('{"hooks": {"PreToolUse": [], "Stop": []}}')
        repo.mkdir()
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        (repo / ".codex").mkdir()
        (repo / ".codex/config.toml").write_text('[mcp_servers.mine]\nurl = "https://x"\n')
        skills_of = lambda p: {"s1": pdir / "skills/s1"}  # noqa: E731
        checks = 0

        def ok(cond, what):
            nonlocal checks
            checks += 1
            if not cond:
                sys.exit(f"self-test failed: {what}")

        def quiet(*a):
            import contextlib
            import io
            with contextlib.redirect_stdout(io.StringIO()):
                return sync_tools(*a)

        ex = quiet(repo, src, skills_of, ["m"], [], False)
        settings = json.loads((repo / ".claude/settings.local.json").read_text())
        ok(settings["enabledPlugins"] == {"m@4nrry": True}, "claude enables the plugin")
        codex_cfg = tomllib.loads((repo / ".codex/config.toml").read_text())
        ok("plugins" not in codex_cfg and codex_cfg["mcp_servers"]["srv"]["args"][1:] == ["m", "srv"],
           "codex gets the MCP server, not the plugin (whose skills it would list twice)")
        ok(list(codex_cfg["hooks"]) == ["PreToolUse"]
           and codex_cfg["hooks"]["PreToolUse"][0]["hooks"][0]["command"].endswith("PreToolUse --plugin m --json"),
           "codex gets the supported hooks inline")
        ok("mine" in codex_cfg["mcp_servers"], "codex keeps the hand-written server")
        grok_cfg = tomllib.loads((repo / ".grok/config.toml").read_text())
        ok(grok_cfg["mcp_servers"]["srv"]["args"][1:] == ["m", "srv"], "grok gets the MCP server")
        hooks = json.loads((repo / ".grok/hooks/4nrry-m.json").read_text())["hooks"]
        ok(list(hooks) == ["PreToolUse"], "grok hooks only for supported events")
        ok((repo / ".agents/plugins/m/skills/s1/SKILL.md").is_file()
           and not (repo / ".agents/plugins/m/skills/s1").is_symlink(), "antigravity gets a real copy")
        ok(json.loads((repo / ".agents/plugins/m/mcp_config.json").read_text())["mcpServers"]["srv"]["command"]
           == "python3", "antigravity gets the MCP server")
        ok(set(ex) == {".claude/settings.local.json", ".grok/config.toml", ".grok/hooks/4nrry-m.json",
                       ".agents/plugins/m/"},
           "excludes cover the files only this script wrote, not a hand-written codex file")
        before = (repo / ".grok/config.toml").read_text()
        quiet(repo, src, skills_of, ["m"], ["m"], False)
        ok((repo / ".grok/config.toml").read_text() == before, "a second run changes nothing")
        quiet(repo, src, skills_of, [], ["m"], False)
        ok(not (repo / ".claude/settings.local.json").exists(), "claude entry removed, empty file with it")
        ok((repo / ".codex/config.toml").read_text() == '[mcp_servers.mine]\nurl = "https://x"\n',
           "codex back to the hand-written file")
        ok(not (repo / ".grok/config.toml").exists() and not (repo / ".grok/hooks/4nrry-m.json").exists(),
           "grok files removed")
        ok(not (repo / ".agents/plugins/m").exists(), "antigravity folder removed")
        (repo / ".agents/plugins/m").mkdir(parents=True)
        quiet(repo, src, skills_of, ["m"], [], False)
        ok(not (repo / ".agents/plugins/m/plugin.json").exists(), "a folder not ours is left alone")
        subprocess.run(["git", "-C", str(repo), "add", ".codex/config.toml"], check=True)
        (repo / ".codex/config.toml").write_text("")
        subprocess.run(["git", "-C", str(repo), "add", ".codex/config.toml"], check=True)
        quiet(repo, src, skills_of, ["m"], ["m"], False)
        ok((repo / ".codex/config.toml").read_text() == "", "a tracked codex file is not changed")

        # Review cases: broken markers, odd settings, hand-written servers, a bad skill, a subfolder.
        g = repo / ".grok/config.toml"
        g.write_text(f"{BEGIN}\n[mine]\nkeep = 1\n")
        quiet(repo, src, skills_of, ["m"], ["m"], False)
        quiet(repo, src, skills_of, ["m"], ["m"], False)
        ok(g.read_text() == f"{BEGIN}\n[mine]\nkeep = 1\n", "a broken marker pair leaves the file alone")
        g.write_text('[mcp_servers.srv]\ncommand = "own"\n')
        quiet(repo, src, skills_of, ["m"], ["m"], False)
        ok(tomllib.loads(g.read_text())["mcp_servers"]["srv"]["command"] == "own", "a hand-written server is kept")
        g.write_text('[mcp_servers."srv"]   # mine\ncommand = "own"\n')
        quiet(repo, src, skills_of, ["m"], ["m"], False)
        ok(tomllib.loads(g.read_text())["mcp_servers"]["srv"]["command"] == "own"
           and BEGIN not in g.read_text(), "a hand-written header with a comment is seen")
        ok(q("/x/\U0001f600") == '"/x/\U0001f600"' and tomllib.loads(f"a = {q(chr(0x1f600))}")["a"] == chr(0x1f600),
           "a non-BMP path stays valid TOML")
        g.write_text("[mcp_servers]\nsrv = 1\n")
        quiet(repo, src, skills_of, ["m"], ["m"], False)
        ok(g.read_text() == "[mcp_servers]\nsrv = 1\n", "a block that would not parse beside the file is not written")
        (repo / ".claude/settings.local.json").write_text("[]")
        quiet(repo, src, skills_of, ["m"], ["m"], False)
        ok((repo / ".claude/settings.local.json").read_text() == "[]", "odd settings are left alone")
        copy = repo / ".agents/plugins/m"
        if copy.exists():
            import shutil as _sh
            _sh.rmtree(copy)
        quiet(repo, src, skills_of, ["m"], ["m"], False)
        (pdir / "skills/s1/SKILL.md").write_text("---\nname: s1\ndescription: changed\n---\n")
        quiet(repo, src, skills_of, ["m"], ["m"], False)
        ok("changed" in (copy / "skills/s1/SKILL.md").read_text(), "an edited skill refreshes the copy")
        (pdir / "skills/s1/dangling").symlink_to(t / "nowhere")
        quiet(repo, src, skills_of, ["m"], ["m"], False)
        ok((copy / OWNED).exists() and "changed" in (copy / "skills/s1/SKILL.md").read_text(),
           "a failed copy keeps the old one")
        (pdir / "skills/s1/dangling").unlink()
        sub_dir = repo / "sub"
        (sub_dir / ".codex").mkdir(parents=True)
        (sub_dir / ".codex/config.toml").write_text("")
        subprocess.run(["git", "-C", str(repo), "add", "sub/.codex/config.toml"], check=True)
        quiet(sub_dir, src, skills_of, ["m"], [], False)
        ok((sub_dir / ".codex/config.toml").read_text() == "", "a tracked file in a subfolder is not changed")
    print(f"self-test: {checks} checks ok")
    return 0


if __name__ == "__main__":
    import sys
    if sys.argv[1:] == ["--self-test"]:
        sys.exit(self_test())
    sys.exit(__doc__.strip().splitlines()[0])
