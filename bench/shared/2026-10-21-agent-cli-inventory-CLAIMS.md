# Agent CLI inventory, 2026-10-21 — claims

**Notes, not run records.** Versions installed on the author's machine (Kubuntu,
x86-64) on 2026-10-21, and how each row of
`plugins/crew/references/clis.md` was confirmed for that
version. Refresh with each tool's `--version`; on a version change, re-check
the rows marked "help" or "listing" before trusting them.

| Tool | Version | Binary (first on PATH) | Confirmed by |
|---|---|---|---|
| Claude Code | 2.1.307 | `~/.local/bin/claude` | help; `claude plugin list`; its embedded deep-research script is byte-identical to 2.1.306's (template literal sha256 `4bf8862ee44a…`), so agent-fleet's fork needs no rebase |
| Antigravity CLI `agy` | 1.4.4 | `~/.local/bin/agy` | help; `agy plugin list --json`; a `-p` run listing skills |
| opencode | 2.1.2 | `~/.opencode/bin/opencode` | help; a `run` listing skills |
| GitHub Copilot CLI | 1.0.102 | `~/.local/bin/copilot` (shadows VS Code's `/usr/bin/copilot` shim) | help; `copilot skill list --json` |
| GitHub Copilot desktop app | engine CLI 1.0.99-2 | `~/AppImages/github_copilot.appimage` | bundled SDK's skill scopes |
| VS Code (built-in Copilot 0.71.0) | 1.143.0 | `/usr/bin/code` | docs only |
| Grok Build | 1.0.62 | `~/.local/bin/grok` | help; `grok inspect --json` |
| Hermes Agent | 0.22.4 | `~/.local/bin/hermes` | help; source at 4d04303; `hermes skills list` |
| Codex CLI | 0.163.0 | `~/.local/bin/codex` | help; `codex debug prompt-input`; `codex plugin list` |
| ChatGPT app | 26.1016.51333 (bundled Codex 0.163.0-alpha.11) | `/usr/bin/chatgpt` | bundled files; shares `~/.codex` |
| Cursor IDE / `cursor-agent` | 3.26.16 / 2026.10.19-6bbf2c4 | `~/.local/bin/cursor-agent` | help; docs; app bundle strings |
| Muse Code | 1.4.11 | `~/.local/bin/muse` | help; `muse skills list` |
| Kimi Code desktop | 1.1.1 | `/opt/Kimi Code` | docs; app bundle strings |
| Kimi Code CLI | 2.3.0 | `~/.kimi-code/bin/kimi` (not on PATH) | help; a `-p` run's recorded session listed the global and project skills; the run itself failed with 403 (the plan has no Kimi Code access) |
| ZCode desktop | 3.16.2 | `/usr/bin/zcode` (opens the app) | docs; app bundle strings |
| gh | 2.103.0 | `/usr/bin/gh` | help (`gh skill` copies skills; not used) |

Not established: Kimi Code as a worker (no subscription) and ZCode (no CLI);
Cursor, ZCode and the Copilot desktop app loading the linked skills in a live
session.
