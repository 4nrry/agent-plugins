# Batch 2026-10-26-kimi-hooks — claims

**Smoke notes, not run records.** Kimi Code, n=1, on an account without a
plan that includes Kimi Code: every model call ends in `403 Your current
subscription does not have access to Kimi Code`.

- Kimi's hook contract matches Claude Code's (docs): snake_case JSON on stdin
  with `tool_input.command`, exit 2 blocks with stderr as the reason,
  `hookSpecificOutput.permissionDecision: "deny"` blocks, stdout of
  `UserPromptSubmit` is appended to the context. Its tools are named `Bash`,
  `Read`, `Write`, `Edit` (bundle), so Claude matchers apply unchanged; `Write`
  takes `path`, which the dispatcher aliases to `file_path`.
- Live: with the two `[[hooks]]` entries running `adapters/claude_hooks.py`,
  `kimi -p 'Use grok for this: reply pong'` emitted "The crew skill may apply
  (matched: grok)" before the 403.
- Not verified: `PreToolUse` (needs a model to call a tool) and the Kinocut MCP
  connection (Kimi reports MCP status only in its TUI, `/mcp`, and starts no
  server before the failed model call). The entry follows Kimi's documented
  `mcpServers` schema and uses the launcher that connected under Hermes's
  filtered PATH.
