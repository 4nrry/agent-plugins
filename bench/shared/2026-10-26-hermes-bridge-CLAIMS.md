# Batch 2026-10-26-hermes-bridge — claims

**Smoke notes, not run records.** Hermes 0.22.5 (`xai-oauth:grok-4.7`), n=1 per
case, with `4nrry-bridge` linked from the worktree and enabled.

| Case | Result |
|---|---|
| crew's UserPromptSubmit hook through `pre_llm_call`, prompt naming grok | the model quoted "The crew skill may apply" from its own message |
| media-agent's PreToolUse hook through `pre_tool_call` + `transform_tool_result`, `echo vipsthumbnail in.jpg -s 480 -o thumb.png` | the terminal result came back with the `[hook]` warning appended |
| `hermes mcp add kinocut` with `mcp_launch.py` | discovery found 203 tools and saved the server |
| the same server inside the running gateway | "Connection closed": Hermes gives MCP servers a filtered environment, and `uvx` lives in Homebrew, outside that PATH. Fixed in `mcp_launch.py`, which also searches `~/.local/bin`, Homebrew and `/usr/local/bin`; an MCP `initialize` with `PATH=/usr/bin:/bin` then answered. The gateway parks a failed server until a reconnect, so the live session check waits for a gateway restart or `/reload-mcp` |
| opencode bridge in a real session (global config, linked from the clone) | the crew line, 203 Kinocut tools and a crew call to grok all worked |
