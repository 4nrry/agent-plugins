# Batch 2026-10-26-zcode-muse — claims

**Smoke notes, not run records.** ZCode's bundled CLI 0.17.0 and Muse Code
1.4.13, n=1 each, no model calls: ZCode's bundled CLI cannot locate its
provider config headless, and Muse ran on its `echo` provider.

- ZCode installs Claude Code marketplaces: `zcode plugins marketplace add` on
  the clone, then installing crew, agent-fleet and media-agent loaded their
  skills, hooks and the Kinocut MCP server. Each skill then showed twice
  (`crew` linked, `crew:crew` from the plugin), so the plugins were removed
  (`--force`) and the hooks and server went into `~/.zcode/cli/config.json`
  instead: `hooks.events` `process` entries running `adapters/claude_hooks.py`,
  `mcp.servers.kinocut` through `adapters/mcp_launch.py`. `zcode doctor`
  reported no hook or MCP error. Not verified live: `zcode -p` fails before any
  hook with "无法定位 CLI ZCode Built-in Provider Config".
- Muse reads Agent Plugins bundles: `muse plugins validate` on each plugin
  lists its skills and media-agent's `kinocut`, but no hooks: the root
  `plugin.json` makes `.claude-plugin/` an inactive overlay, and
  `hooks/hooks.json` is not part of Agent Plugins.
- Muse's user hooks speak Claude's contract. Live, with `--provider echo` and a
  capture hook: the `UserPromptSubmit` payload was
  `{cwd, hook_event_name, model, permission_mode, prompt, session_id, turn_id}`,
  and `claude_hooks.py` returned "The crew skill may apply (matched: codex
  grok)". The hook environment is cleared to HOME, LANG, LOGNAME, PATH, PWD,
  SHELL, USER, MUSE_SESSION_ID, MUSE_THREAD_ID, TRACEPARENT; PATH is kept.
- Muse's shell tools are `bash`, `exec_command` and `shell` (binary strings:
  `SHELL_TOOLS = {"bash", "exec_command", "shell"}`), so the dispatcher now
  maps lowercase and Codex-style names to Claude's and aliases `cmd` to
  `command`. Not verified live: `PreToolUse` (the echo provider calls no tool).
- Muse starts MCP servers even on `echo`: with `kinocut` set to `required`,
  a broken command failed the run ("Required MCP server `kinocut` failed during
  startup") and the launcher entry passed (exit 0, 3 s). The launcher under
  Muse's hook PATH listed 203 Kinocut tools.
