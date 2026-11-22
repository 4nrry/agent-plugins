#!/usr/bin/env python3
"""Turn a plugin on for one project in every agent tool that has a project scope.

`link_skills.py project DIR PLUGIN...` calls this after linking the skills into
DIR/.agents/skills (which Codex, Copilot, Cursor, Grok, opencode and Hermes read).
The rest of a plugin, its MCP servers and hooks, goes where each tool reads a
project's own config:

  Claude Code  .claude/settings.local.json  enabledPlugins["<plugin>@4nrry"]
  Codex        .codex/config.toml           [plugins."<plugin>@4nrry"]   (skipped when the file is tracked)
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
import json
import shutil
import subprocess
from pathlib import Path

MARKETPLACE_NAME = "4nrry"
BEGIN = "# >>> link_skills.py (agent-plugins)"
END = "# <<< link_skills.py"
OWNED = ".link_skills"  # marker file inside a folder this script owns


def tracked(repo: Path, rel: str) -> bool:
    if not (repo / ".git").exists():
        return False
    return subprocess.run(["git", "-C", str(repo), "ls-files", "--error-unmatch", rel],
                          capture_output=True).returncode == 0


def toml_block(path: Path, body: str, dry: bool) -> bool:
    """Replace the marked block in a TOML file with body (empty removes it).
    Returns True when the file changed."""
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    lines = text.split("\n")
    if BEGIN in lines and END in lines[lines.index(BEGIN):]:
        i = lines.index(BEGIN)
        j = i + lines[i:].index(END)
        lines = lines[:i] + lines[j + 1:]
    rest = "\n".join(lines).strip("\n")
    new = rest
    if body:
        new = (rest + "\n\n" if rest else "") + f"{BEGIN}\n{body.strip()}\n{END}"
    new = new + "\n" if new else ""
    if new == text or (not new and not path.exists()):
        return False
    if not dry:
        if new:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(new, encoding="utf-8")
        else:
            path.unlink()
    return True


def outside_block_has(path: Path, header: str) -> bool:
    if not path.exists():
        return False
    lines = path.read_text(encoding="utf-8").split("\n")
    if BEGIN in lines and END in lines[lines.index(BEGIN):]:
        i = lines.index(BEGIN)
        lines = lines[:i] + lines[i + lines[i:].index(END) + 1:]
    return header in (line.strip() for line in lines)


def q(s: str) -> str:
    return json.dumps(s)


def mcp_servers(plugin_dir: Path) -> dict:
    try:
        return json.loads((plugin_dir / "mcp.json").read_text(encoding="utf-8")).get("mcpServers", {}) or {}
    except (OSError, ValueError):
        return {}


def hook_events(plugin_dir: Path) -> list:
    try:
        spec = json.loads((plugin_dir / "hooks" / "hooks.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return sorted(e for e in spec.get("hooks", {}) if e in ("PreToolUse", "PostToolUse", "UserPromptSubmit"))


def claude(repo: Path, plugins: list, gone: list, dry: bool, log: list) -> None:
    path = repo / ".claude/settings.local.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except ValueError:
        log.append(f"  ! {path} is not valid JSON; left alone")
        return
    enabled = data.setdefault("enabledPlugins", {})
    before = dict(enabled)
    for p in plugins:
        enabled[f"{p}@{MARKETPLACE_NAME}"] = True
    for p in gone:
        enabled.pop(f"{p}@{MARKETPLACE_NAME}", None)
    if not enabled:
        data.pop("enabledPlugins")
    if enabled != before:
        log.append(f"  claude: {path.relative_to(repo)}")
        if not dry:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def codex(repo: Path, plugins: list, dry: bool, log: list) -> list:
    rel = ".codex/config.toml"
    path = repo / rel
    if tracked(repo, rel):
        if plugins:
            log.append(f"  ! codex: {rel} is tracked by git; not changed (Codex gets the skills only)")
        return []
    body = []
    for p in plugins:
        header = f'[plugins."{p}@{MARKETPLACE_NAME}"]'
        if outside_block_has(path, header):
            log.append(f"  ! codex: {rel} already has {header} outside the managed block; kept as is")
            continue
        body.append(f"{header}\nenabled = true")
    if toml_block(path, "\n\n".join(body), dry):
        log.append(f"  codex: {rel}")
    return [f"/{rel}"] if (path.exists() or body) else []


def grok(repo: Path, source: Path, plugins: list, gone: list, dry: bool, log: list) -> list:
    rel = ".grok/config.toml"
    launch = source / "adapters/mcp_launch.py"
    hooks_py = source / "adapters/claude_hooks.py"
    body, excludes = [], []
    for p in plugins:
        pdir = source / "plugins" / p
        for server in sorted(mcp_servers(pdir)):
            body.append(f"[mcp_servers.{server}]\ncommand = \"python3\"\n"
                        f"args = [{q(str(launch))}, {q(p)}, {q(server)}]")
        events = hook_events(pdir)
        hook_file = repo / f".grok/hooks/4nrry-{p}.json"
        if events:
            spec = {"hooks": {e: [{"hooks": [{"type": "command", "command": "python3",
                                               "args": [str(hooks_py), e, "--plugin", p, "--json"]}]}]
                              for e in events}}
            new = json.dumps(spec, indent=2) + "\n"
            if not hook_file.exists() or hook_file.read_text(encoding="utf-8") != new:
                log.append(f"  grok: {hook_file.relative_to(repo)}")
                if not dry:
                    hook_file.parent.mkdir(parents=True, exist_ok=True)
                    hook_file.write_text(new, encoding="utf-8")
            excludes.append(f"/.grok/hooks/4nrry-{p}.json")
    for p in gone:
        hook_file = repo / f".grok/hooks/4nrry-{p}.json"
        if hook_file.exists():
            log.append(f"  grok: - {hook_file.relative_to(repo)}")
            if not dry:
                hook_file.unlink()
    if tracked(repo, rel):
        if body:
            log.append(f"  ! grok: {rel} is tracked by git; MCP servers not added")
    else:
        if toml_block(repo / rel, "\n\n".join(body), dry):
            log.append(f"  grok: {rel}")
        if (repo / rel).exists() or body:
            excludes.append(f"/{rel}")
    return excludes


def antigravity(repo: Path, source: Path, skills_of, plugins: list, gone: list, dry: bool, log: list) -> list:
    launch = source / "adapters/mcp_launch.py"
    excludes = []
    for p in gone:
        folder = repo / f".agents/plugins/{p}"
        if (folder / OWNED).exists():
            log.append(f"  antigravity: - {folder.relative_to(repo)}")
            if not dry:
                shutil.rmtree(folder)
    for p in plugins:
        pdir = source / "plugins" / p
        folder = repo / f".agents/plugins/{p}"
        if folder.exists() and not (folder / OWNED).exists():
            log.append(f"  ! antigravity: {folder.relative_to(repo)} exists and is not this script's; left alone")
            continue
        excludes.append(f"/.agents/plugins/{p}/")
        try:
            manifest = json.loads((pdir / "plugin.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            manifest = {"name": p}
        servers = {s: {"command": "python3", "args": [str(launch), p, s]} for s in sorted(mcp_servers(pdir))}
        files = {"plugin.json": {k: manifest[k] for k in ("name", "version", "description") if k in manifest}}
        if servers:
            files["mcp_config.json"] = {"mcpServers": servers}
        stamp = manifest.get("version", "") + "\n" + "\n".join(sorted(skills_of(p)))
        current = (folder / OWNED).read_text(encoding="utf-8") if (folder / OWNED).exists() else None
        same = current == stamp and all(
            (folder / n).exists() and json.loads((folder / n).read_text(encoding="utf-8")) == v
            for n, v in files.items())
        if same:
            continue
        log.append(f"  antigravity: {folder.relative_to(repo)} ({len(skills_of(p))} skills copied)")
        if dry:
            continue
        if folder.exists():
            shutil.rmtree(folder)
        (folder / "skills").mkdir(parents=True)
        for name, target in sorted(skills_of(p).items()):
            shutil.copytree(target, folder / "skills" / name, symlinks=False)
        for name, value in files.items():
            (folder / name).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
        (folder / OWNED).write_text(stamp, encoding="utf-8")
    return excludes


def sync_tools(repo: Path, source: Path, skills_of, plugins: list, previous: list, dry: bool) -> list:
    """Write every tool's project config for plugins; remove it for previous - plugins.
    skills_of(plugin) -> {skill name: skill dir}. Returns the paths to git-exclude."""
    gone = sorted(set(previous) - set(plugins))
    log = []
    claude(repo, plugins, gone, dry, log)
    excludes = codex(repo, plugins, dry, log)
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
        projects = tomllib.loads((home / ".codex/config.toml").read_text(encoding="utf-8")).get("projects", {})
        if projects.get(str(repo), {}).get("trust_level") != "trusted":
            notes.append("Codex: not trusted, so .codex/config.toml is ignored "
                         f"(trust it, or add [projects.\"{repo}\"] trust_level = \"trusted\")")
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
        ok(codex_cfg["plugins"]["m@4nrry"]["enabled"] is True, "codex enables the plugin")
        ok("mine" in codex_cfg["mcp_servers"], "codex keeps the hand-written server")
        grok_cfg = tomllib.loads((repo / ".grok/config.toml").read_text())
        ok(grok_cfg["mcp_servers"]["srv"]["args"][1:] == ["m", "srv"], "grok gets the MCP server")
        hooks = json.loads((repo / ".grok/hooks/4nrry-m.json").read_text())["hooks"]
        ok(list(hooks) == ["PreToolUse"], "grok hooks only for supported events")
        ok((repo / ".agents/plugins/m/skills/s1/SKILL.md").is_file()
           and not (repo / ".agents/plugins/m/skills/s1").is_symlink(), "antigravity gets a real copy")
        ok(json.loads((repo / ".agents/plugins/m/mcp_config.json").read_text())["mcpServers"]["srv"]["command"]
           == "python3", "antigravity gets the MCP server")
        ok(set(ex) >= {"/.codex/config.toml", "/.grok/config.toml", "/.grok/hooks/4nrry-m.json",
                       "/.agents/plugins/m/"}, "excludes cover the written files")
        before = (repo / ".grok/config.toml").read_text()
        quiet(repo, src, skills_of, ["m"], ["m"], False)
        ok((repo / ".grok/config.toml").read_text() == before, "a second run changes nothing")
        quiet(repo, src, skills_of, [], ["m"], False)
        ok("enabledPlugins" not in json.loads((repo / ".claude/settings.local.json").read_text()),
           "claude entry removed")
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
    print(f"self-test: {checks} checks ok")
    return 0


if __name__ == "__main__":
    import sys
    if sys.argv[1:] == ["--self-test"]:
        sys.exit(self_test())
    sys.exit(__doc__.strip().splitlines()[0])
