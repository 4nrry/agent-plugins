// opencode 2.x plugin: runs the Claude Code hooks and the MCP servers of this
// marketplace's portable plugins (the ones with an Agent Plugins plugin.json)
// inside opencode, from the same files Claude Code uses, so there is no second
// copy to keep in sync. link_skills.py links it into ~/.config/opencode/plugins/.
//
// Mapping (Claude hook contract -> opencode):
//   UserPromptSubmit  -> session "prompt": run with {"prompt": text}; its stdout
//                        (or additionalContext) is added to the system prompt of
//                        the model calls that follow, until the next prompt.
//   PreToolUse        -> tool "execute.before": run with {"tool_name",
//                        "tool_input"} in Claude's names; a deny (or exit 2)
//                        throws, which blocks the call; additionalContext goes to
//                        the next model call.
//   Other events, and matchers for tools opencode lacks (Workflow), are skipped.
//   mcp.json servers  -> ctx.mcp.transform, as local servers.
// A plugin runs only when it is listed in adapters/global-plugins.json, or when
// the session folder (or a parent) links one of its skills in .agents/skills,
// as `link_skills.py project` does. Inside a crew worker run (CREW_RUN set) the
// bridge does nothing, so the worker stays isolated.
import { spawnSync } from "node:child_process";
import { existsSync, readFileSync, readdirSync, readlinkSync } from "node:fs";
import { homedir } from "node:os";
import { basename, dirname, join, resolve, sep } from "node:path";

const MARKETPLACE = process.env.AGENT_PLUGINS_MARKETPLACE || join(homedir(), ".claude/plugins/marketplaces/4nrry");
const HOOK_TIMEOUT_MS = 30000;
// opencode tool -> [Claude tool, {opencode arg: Claude arg}]
const TOOLS = {
  bash: ["Bash", { command: "command", workdir: "cwd" }],
  shell: ["Bash", { command: "command", workdir: "cwd" }],
  read: ["Read", { filePath: "file_path", path: "file_path" }],
  write: ["Write", { filePath: "file_path", path: "file_path", content: "content" }],
  edit: ["Edit", { filePath: "file_path", path: "file_path", oldString: "old_string", newString: "new_string" }],
  glob: ["Glob", { pattern: "pattern", path: "path" }],
  grep: ["Grep", { pattern: "pattern", path: "path", include: "glob" }],
};

function readJson(path) {
  try { return JSON.parse(readFileSync(path, "utf8")); } catch { return null; }
}

// Plugins whose skills are linked into .agents/skills of start or a parent
// below the home folder (~/.agents/skills is the global root, not a project).
function projectNames(start) {
  const names = new Set();
  const home = resolve(homedir());
  for (let dir = resolve(start); dir !== home && dir.startsWith(home + sep); dir = dirname(dir)) {
    const skills = join(dir, ".agents", "skills");
    let entries = [];
    try { entries = readdirSync(skills, { withFileTypes: true }); } catch {}
    for (const e of entries) {
      if (!e.isSymbolicLink()) continue;
      let target = "";
      try { target = readlinkSync(join(skills, e.name)); } catch { continue; }
      const parts = target.split(/[\\/]/);
      const i = parts.lastIndexOf("plugins");
      if (i >= 0 && i + 1 < parts.length) names.add(parts[i + 1]);
    }
  }
  return names;
}

function portablePlugins(start) {
  const dir = join(MARKETPLACE, "plugins");
  if (!existsSync(dir)) return [];
  const all = readdirSync(dir).map((name) => join(dir, name)).filter((root) => existsSync(join(root, "plugin.json")));
  // An unreadable or malformed list falls back to every plugin, as before the list existed.
  const listed = readJson(join(MARKETPLACE, "adapters", "global-plugins.json"));
  if (!Array.isArray(listed) || !listed.every((n) => typeof n === "string")) return all;
  const wanted = new Set([...listed, ...projectNames(start)]);
  return all.filter((root) => wanted.has(basename(root)));
}

function hooksOf(root, event) {
  const spec = readJson(join(root, "hooks", "hooks.json"));
  return ((spec && spec.hooks && spec.hooks[event]) || []).flatMap((group) =>
    (group.hooks || []).filter((h) => h.type === "command").map((h) => ({ matcher: group.matcher, command: h.command, root })));
}

function matches(matcher, tool) {
  if (!matcher || matcher === "*") return true;
  try { return new RegExp(`^(?:${matcher})$`).test(tool); } catch { return matcher === tool; }
}

// Runs one hook command; returns {block, reason, context}.
function run(hook, payload) {
  const p = spawnSync("bash", ["-c", hook.command], {
    input: JSON.stringify(payload), encoding: "utf8", timeout: HOOK_TIMEOUT_MS,
    env: { ...process.env, CLAUDE_PLUGIN_ROOT: hook.root },
  });
  if (p.status === 2) return { block: true, reason: (p.stderr || "blocked by a hook").trim() };
  const out = (p.stdout || "").trim();
  if (!out) return {};
  let json = null;
  try { json = JSON.parse(out); } catch { return { context: out }; }
  const specific = json.hookSpecificOutput || {};
  if (specific.permissionDecision === "deny" || json.decision === "block") {
    return { block: true, reason: specific.permissionDecisionReason || json.reason || "blocked by a hook" };
  }
  return { context: specific.additionalContext || json.additionalContext || "" };
}

export default {
  id: "4nrry-bridge",
  async setup(ctx) {
    if (process.env.CREW_RUN) return;
    const plugins = portablePlugins(ctx.directory || process.cwd());
    const pending = new Map(); // sessionID -> [context text]
    const add = (sessionID, text) => {
      if (!text) return;
      const key = sessionID || "_";
      pending.set(key, [...(pending.get(key) || []), text]);
    };

    await ctx.mcp.transform((editor) => {
      for (const root of plugins) {
        const servers = (readJson(join(root, "mcp.json")) || {}).mcpServers || {};
        for (const [name, s] of Object.entries(servers)) {
          if ((s.type || "stdio") !== "stdio" || !s.command) continue;
          editor.set(name, { type: "local", command: [s.command, ...(s.args || [])], ...(s.env ? { environment: s.env } : {}) });
        }
      }
    });

    await ctx.session.hook("prompt", (event) => {
      const text = (event.prompt && event.prompt.text) || "";
      pending.delete(event.sessionID || "_");
      for (const root of plugins) {
        for (const hook of hooksOf(root, "UserPromptSubmit")) {
          add(event.sessionID, run(hook, { hook_event_name: "UserPromptSubmit", prompt: text }).context);
        }
      }
    });

    await ctx.session.hook("context", (event) => {
      for (const text of pending.get(event.sessionID || "_") || []) event.system.push({ type: "text", text });
    });

    await ctx.tool.hook("execute.before", (event) => {
      const [tool, keys] = TOOLS[String(event.tool)] || [];
      if (!tool) return;
      const input = {};
      for (const [k, v] of Object.entries(event.input || {})) input[keys[k] || k] = v;
      for (const root of plugins) {
        for (const hook of hooksOf(root, "PreToolUse").filter((h) => matches(h.matcher, tool))) {
          const r = run(hook, { hook_event_name: "PreToolUse", tool_name: tool, tool_input: input });
          if (r.block) throw new Error(r.reason);
          add(event.sessionID, r.context);
        }
      }
    });
  },
};
