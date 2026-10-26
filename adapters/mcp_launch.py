#!/usr/bin/env python3
"""Start one MCP server declared in a plugin's Agent Plugins mcp.json.

  mcp_launch.py PLUGIN SERVER

For tools that take an MCP command but cannot install the plugin (Hermes, Kimi,
Muse, ZCode): register `python3 <marketplace clone>/adapters/mcp_launch.py
media-agent kinocut` once, and the server's command, arguments and version pin
stay in the plugin's mcp.json, updated with the marketplace. Stdlib only.
"""
import json
import os
import shutil
import sys
from pathlib import Path

MARKETPLACE = Path(__file__).resolve().parent.parent
# Hermes hands MCP servers a filtered environment whose PATH can miss where uv
# and node live (Homebrew on Linux, ~/.local/bin), so look there too.
EXTRA_PATH = [Path.home() / ".local/bin", Path("/home/linuxbrew/.linuxbrew/bin"), Path("/opt/homebrew/bin"),
              Path("/usr/local/bin"), Path.home() / ".cargo/bin"]


def server(plugin: str, name: str) -> dict:
    path = MARKETPLACE / "plugins" / plugin / "mcp.json"
    try:
        spec = json.loads(path.read_text(encoding="utf-8"))["mcpServers"][name]
    except (OSError, ValueError, KeyError) as exc:
        sys.exit(f"mcp_launch: no server {name!r} in {path} ({exc})")
    if spec.get("type", "stdio") != "stdio" or not spec.get("command"):
        sys.exit(f"mcp_launch: {name!r} is not a stdio server")
    return spec


def executable(command: str) -> str:
    path = os.pathsep.join([os.environ.get("PATH", ""), *map(str, EXTRA_PATH)])
    found = shutil.which(command, path=path)
    if not found:
        sys.exit(f"mcp_launch: {command!r} not found on PATH or in {', '.join(map(str, EXTRA_PATH))}")
    return found


def self_test() -> int:
    spec = server("media-agent", "kinocut")
    assert spec["command"] and isinstance(spec.get("args", []), list), spec
    assert os.path.isabs(executable("python3"))
    print("self-test: ok")
    return 0


def main() -> int:
    if sys.argv[1:] == ["--self-test"]:
        return self_test()
    if len(sys.argv) != 3:
        sys.exit(__doc__.strip().splitlines()[2])
    spec = server(sys.argv[1], sys.argv[2])
    os.environ.update({k: str(v) for k, v in (spec.get("env") or {}).items()})
    if spec.get("cwd"):
        os.chdir(MARKETPLACE / "plugins" / sys.argv[1] / spec["cwd"])
    command = executable(spec["command"])
    os.environ["PATH"] = os.pathsep.join([str(Path(command).parent), os.environ.get("PATH", "")])
    os.execv(command, [command, *spec.get("args", [])])
    return 1


if __name__ == "__main__":
    sys.exit(main())
