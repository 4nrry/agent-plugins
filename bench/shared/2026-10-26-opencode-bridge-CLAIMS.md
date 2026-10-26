# Batch 2026-10-26-opencode-bridge — claims

**Smoke notes, not run records.** opencode 2.1.4, `deepseek-v4.1-flash-free`,
n=1 per case, with the bridge loaded from an isolated `OPENCODE_CONFIG_DIR`.

| Case | Result |
|---|---|
| Plugin load | `setup` ran and found the 3 portable plugins (crew, agent-fleet, media-agent) |
| `session` "prompt" and "context" hooks | both carry `sessionID`; "context" also has `system`, `messages`, `tools` |
| crew's UserPromptSubmit hook, prompt naming grok | the model quoted "The crew skill may apply (matched: grok)." from its system prompt |
| media-agent's PreToolUse hook, `echo vipsthumbnail in.jpg -s 480 -o thumb.png` | opencode calls the tool `shell`; the warning reached the next model call |
| media-agent's `mcp.json` through `ctx.mcp.transform` | "mcp connected server=kinocut tools=203"; the model listed `video_*` tools |
| baseline without the bridge | 3 s; with it, 7 s for the same one-line reply |

The first probe hung for the whole 240 s timeout, as opencode's start has done
before without any plugin; the same setup then ran in 7 s and 24 s.
agent-fleet's PreToolUse hook matches `Workflow`, a Claude Code tool, and never
fires in opencode.
