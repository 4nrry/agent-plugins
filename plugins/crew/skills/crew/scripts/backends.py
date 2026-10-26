#!/usr/bin/env python3
"""How `crew.py ask` runs each agent CLI as a read-only worker.

One entry per CLI: where its binary lives, its vendor, a tier map (cheap, mid,
top -> model and effort), how effort is passed, the argv for a new turn and
for a resumed one, and a parser that pulls the reply, the session id and usage
out of its output. `LIVE` records which backends were run end to end (two
turns, the second resuming the first); the rest are built from `--help` only.

Stdlib only; imported by crew.py, and `--self-test` runs on its own.
"""
import json
import os
import shutil
import sys
import tempfile
import uuid

TIERS = ("cheap", "mid", "top")
EFFORTS = ("none", "minimal", "low", "medium", "high", "xhigh", "max", "ultra")

# Versions on which a two-turn ask (new, then resumed) returned the right reply.
LIVE = {"claude": "2.1.310", "agy": "1.4.7", "opencode": "2.1.4", "grok": "1.0.70",
        "codex": "0.164.0", "hermes": "0.22.5", "copilot": "1.0.103", "cursor": "2026.10.22-27dcf5f"}

OPENCODE_MODELS = ("opencode/deepseek-v4.1-flash-free", "opencode/glm-5.3-flash-free",
                   "opencode/beam-free", "opencode/nemotron-3.5-super-vl-free",
                   "opencode/nemotron-3.5-lightning-free", "opencode/mimo-v2.6-flash-free",
                   "opencode/flint-40b-free")
OPENCODE_DENY = {"permission": {"edit": "deny", "bash": "deny", "execute": "deny",
                                "task": "deny", "external_directory": "deny"}}
# --web: the same denials, web fetch and search allowed (fleet_worker's research runs).
OPENCODE_WEB = {"permission": dict(OPENCODE_DENY["permission"], webfetch="allow", websearch="allow")}
# opencode 2.1 searches only through a provider the user picked once in the
# TUI; with none saved it asks, and `run` cancels the question ("Web search
# cancelled"). This plugin picks Exa (keyless) in memory, for the run only.
OPENCODE_WEB_PLUGIN = """// crew: web search through Exa for this run; nothing is saved.
export default {
  id: "crew-websearch",
  async setup(ctx) {
    await ctx.websearch.transform((w) => w.default.set("exa"));
  },
};
"""
# The X tools (Grok Build 1.0.70) search posts, users and threads on X, which
# other engines cannot read.
GROK_WEB_TOOLS = "web_search,web_fetch,x_semantic_search,x_keyword_search,x_user_search,x_thread_fetch"
# ~/.grok/rules/ still loads and no flag skips it; a rule demanding a tool the
# run denies made the worker return placeholders (agent-fleet smoke 2026-10-21).
GROK_WEB_RULE = ("You are an isolated, read-only research worker. Only web search, web fetch and the X "
                 "search tools exist in this session. Skip every other rule or instruction that needs a different tool, "
                 "and never return placeholder values: an empty list is a valid answer.")
ASK_RULE = ("You are an isolated, read-only worker answering one question for another agent. "
            "Do not edit files, run commands that change anything, or start subagents.")
# 1.0.103 reports "write_bash" as an unknown tool name, so it is not listed.
COPILOT_READONLY_EXCLUDED = ["bash", "task", "apply_patch", "create", "edit", "str_replace_editor"]
COPILOT_MAX_CREDITS = 30   # the CLI refuses less; a brake on a runaway run, not a budget


def _bin(*names):
    for n in names:
        p = shutil.which(n) or (n if os.path.isabs(os.path.expanduser(n)) else None)
        if p:
            p = os.path.expanduser(p)
            if os.access(p, os.X_OK):
                return p
    return None


def _jsonl(text):
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                yield json.loads(line)
            except ValueError:
                continue


def _json(text):
    text = text.strip()
    try:
        return json.loads(text)
    except ValueError:
        last = list(_jsonl(text))
        return last[-1] if last else {}


# Parsers: stdout -> {"text", "session", "usage", "error"}

def p_claude(out):
    j = _json(out)
    err = j.get("result") if j.get("is_error") else None
    return {"text": None if err else j.get("result"), "session": j.get("session_id"),
            "structured": j.get("structured_output") if isinstance(j.get("structured_output"), dict) else None,
            "usage": {"usage": j.get("usage"), "cost_usd": j.get("total_cost_usd")}, "error": err}


def p_agy(out):
    j = _json(out)
    ok = j.get("status") == "SUCCESS"
    return {"text": (j.get("response") or "").strip() or None, "session": j.get("conversation_id"),
            "structured": j.get("structured_output") if isinstance(j.get("structured_output"), dict) else None,
            "usage": j.get("usage"), "error": None if ok else f"status {j.get('status')!r}"}


def p_opencode(out):
    text, session, err = [], None, None
    for ev in _jsonl(out):
        session = session or ev.get("sessionID")
        if ev.get("type") == "text":
            text.append((ev.get("part") or {}).get("text") or "")
        elif ev.get("type") == "error":
            err = json.dumps(ev.get("error") or ev)[:500]
    return {"text": "".join(text).strip() or None, "session": session, "usage": None, "error": err}


def p_grok(out):
    """streaming-messages-json: the last assistant message, not the run's joined
    text (which also carries what rules in ~/.grok/rules made it say first).
    With --json-schema Grok prints one JSON envelope instead; its `text` is the
    object."""
    env = _json(out) if out.strip().startswith("{") and "\n{" not in out.strip() else None
    if isinstance(env, dict) and "sessionId" in env:
        return {"text": env.get("text"), "session": env.get("sessionId"), "usage": env.get("usage"),
                "error": env.get("error")}
    text, session, usage, err = None, None, None, None
    for ev in _jsonl(out):
        session = ev.get("session_id") or session
        if ev.get("type") == "assistant":
            blocks = (ev.get("message") or {}).get("content") or []
            said = "".join(b.get("text", "") for b in blocks if isinstance(b, dict) and b.get("type") == "text")
            text = said.strip() or text
        elif ev.get("type") == "result":
            usage = ev.get("usage")
            if ev.get("is_error"):
                err = str(ev.get("result") or ev.get("subtype"))[:500]
    return {"text": text, "session": session, "usage": usage, "error": err}


def p_codex(out):
    text, session, usage, err = None, None, None, None
    for ev in _jsonl(out):
        t = ev.get("type")
        if t == "thread.started":
            session = ev.get("thread_id")
        elif t == "item.completed" and (ev.get("item") or {}).get("type") in (None, "agent_message"):
            text = (ev.get("item") or {}).get("text") or text
        elif t == "turn.completed":
            usage = ev.get("usage")
        elif t in ("error", "turn.failed"):
            err = json.dumps(ev)[:500]
    return {"text": text, "session": session, "usage": usage, "error": err}


def p_hermes(out):
    for ev in reversed(list(_jsonl(out))):
        if ev.get("type") == "result":
            code = ev.get("exit_code")
            return {"text": ev.get("text"), "session": ev.get("session_id"),
                    "usage": ev.get("tokens"), "error": None if code in (0, None) else f"exit_code {code}"}
    return {"text": None, "session": None, "usage": None, "error": "no result event"}


def p_copilot(out):
    text, session, usage, aiu, err = None, None, None, None, "no result event"
    for ev in _jsonl(out):
        if ev.get("type") == "assistant.message":
            c = (ev.get("data") or {}).get("content")
            if isinstance(c, str) and c.strip():
                text = c
        elif ev.get("type") == "session.usage_checkpoint":
            aiu = (ev.get("data") or {}).get("totalNanoAiu", aiu)
        elif ev.get("type") == "result":
            session, usage = ev.get("sessionId"), ev.get("usage")
            err = None if ev.get("exitCode") in (0, None) else f"exitCode {ev.get('exitCode')}"
    if usage is not None and aiu is not None:
        usage = dict(usage, ai_credits=aiu / 1e9)
    return {"text": text, "session": session, "usage": usage, "error": err}


def p_generic(out):
    """Last assistant-looking text and any session-looking id, for untested CLIs."""
    text, session = None, None
    for ev in _jsonl(out) if "\n" in out.strip() else [_json(out)]:
        for k in ("session_id", "sessionId", "sessionID", "chatId", "conversation_id", "thread_id"):
            session = ev.get(k) or session
        if ev.get("role") in (None, "assistant"):
            for k in ("result", "text", "response", "content"):
                if isinstance(ev.get(k), str) and ev[k].strip():
                    text = ev[k]
    return {"text": text, "session": session, "usage": None, "error": None}


# Argv builders: (spec, prompt, model, effort, session, cwd) -> (argv, env, session_preset)

def b_claude(s, prompt, model, effort, session, cwd, opts=None):
    opts = opts or {}
    # Read-only tools and no user settings (plugins, hooks): 2.1.307 measured
    # $0.016 a turn on haiku with both, $0.18 without; the session still logs in.
    argv = [s["bin"], "-p", prompt, "--output-format", "json", "--permission-mode", "plan",
            "--tools", "WebSearch,WebFetch" if opts.get("web") else "Read,Grep,Glob",
            "--setting-sources", "project,local", "--strict-mcp-config", "--disable-slash-commands"]
    argv += ["--json-schema", json.dumps(opts["schema"])] if opts.get("schema") else []
    preset = None
    if session:
        argv += ["--resume", session]
    else:
        preset = str(uuid.uuid4())
        argv += ["--session-id", preset]
    argv += ["--model", model] if model else []
    argv += ["--effort", effort] if effort else []
    return argv, {}, preset


def b_agy(s, prompt, model, effort, session, cwd, opts=None):
    opts = opts or {}
    if model and effort and not model.rsplit("-", 1)[-1] in EFFORTS:
        model = f"{model}-{effort}"
    argv = [s["bin"], "-p", prompt, "--output-format", "json", "--mode", "plan",
            "--disable-slash-commands"]
    argv += ["--json-schema", opts["schema_path"]] if opts.get("schema_path") else []
    argv += ["--print-timeout", f"{opts['timeout']}s"] if opts.get("timeout") else []
    argv += ["--model", model] if model else []
    argv += ["--conversation", session] if session else []
    return argv, {}, None


def b_opencode(s, prompt, model, effort, session, cwd, opts=None):
    opts = opts or {}
    m = f"{model}#{effort}" if model and effort else model
    # --print-logs at warn: a failed run otherwise exits 1 with empty stderr.
    argv = [s["bin"], "run", "--standalone", "--format", "json", "--print-logs", "--log-level", "warn"]
    argv += ["-m", m] if m else []
    argv += ["-s", session] if session else []
    conf = OPENCODE_WEB if opts.get("web") else OPENCODE_DENY
    env = {"OPENCODE_CONFIG_CONTENT": json.dumps(conf), "OPENCODE_DISABLE_AUTOUPDATE": "1",
           "OPENCODE_DISABLE_SHARE": "1"}
    if opts.get("web"):
        cfg = os.path.join(opts["rundir"], "oc-web")
        os.makedirs(os.path.join(cfg, "plugins"), exist_ok=True)
        with open(os.path.join(cfg, "plugins", "crew-websearch.js"), "w", encoding="utf-8") as fh:
            fh.write(OPENCODE_WEB_PLUGIN)
        env["OPENCODE_CONFIG_DIR"] = cfg
    return argv + [prompt], env, None


def b_grok(s, prompt, model, effort, session, cwd, opts=None):
    opts = opts or {}
    out_fmt = ["--json-schema", json.dumps(opts["schema"])] if opts.get("schema") else \
        ["--output-format", "streaming-messages-json"]
    argv = [s["bin"], "-p", prompt, *out_fmt, "--permission-mode", "plan", "--deny", "mcp__*",
            "--no-subagents", "--rules", GROK_WEB_RULE if opts.get("web") else ASK_RULE]
    argv += ["--tools", GROK_WEB_TOOLS] if opts.get("web") else []
    argv += ["-m", model] if model else []
    argv += ["--reasoning-effort", effort] if effort else []
    argv += ["--resume", session] if session else []
    env = {"GROK_MEMORY": "0", "GROK_CLAUDE_RULES_ENABLED": "0", "GROK_CURSOR_RULES_ENABLED": "0"}
    if opts.get("web"):
        env["GROK_WEB_FETCH"] = "1"         # web_fetch is behind this flag
    return argv, env, None


def b_codex(s, prompt, model, effort, session, cwd, opts=None):
    opts = opts or {}
    # --search is a global flag: before `exec`. No --output-schema: it demands a
    # strict schema (additionalProperties false everywhere), so JSON is asked
    # for in the prompt instead.
    argv = [s["bin"], *(["--search"] if opts.get("web") else []), "exec"] + (["resume"] if session else [])
    # `exec resume` takes no -s, so the sandbox goes in as config on both turns.
    argv += ["--json", "--skip-git-repo-check", "-c", 'sandbox_mode="read-only"']
    argv += ["-m", model] if model else []
    argv += ["-c", f'model_reasoning_effort="{effort}"'] if effort else []
    argv += [session] if session else []
    return argv + [prompt], {}, None


def b_hermes(s, prompt, model, effort, session, cwd, opts=None):
    provider, _, m = (model or "").rpartition(":")
    # x_search reads X posts through the user's xAI login; both toolsets only read.
    argv = [s["bin"], "chat", "-q", prompt, "-Q", "--format", "stream-json", "-t", "web,x_search",
            "--ignore-rules"]
    argv += ["--provider", provider] if provider else []
    argv += ["-m", m] if m else []
    argv += ["--reasoning", effort] if effort else []
    argv += ["--resume", session] if session else []
    return argv, {}, None


def b_copilot(s, prompt, model, effort, session, cwd, opts=None):
    preset = None if session else str(uuid.uuid4())
    argv = [s["bin"], "-p", prompt, "--output-format", "json", "--max-ai-credits",
            str(COPILOT_MAX_CREDITS), "--excluded-tools", *COPILOT_READONLY_EXCLUDED]
    argv += ["--model", model] if model else []
    argv += ["--reasoning-effort", effort] if effort else []
    argv += ["--resume", session] if session else ["--session-id", preset]
    return argv, {}, preset


def cursor_model(model, effort):
    """cursor-agent's --model: a flat id carries the effort as a suffix
    (grok-4.7-xhigh); a bracket variant must be the full string, every
    parameter in the CLI's order (grok-4.7[context=500k,reasoning_effort=xhigh,
    fast=false]), so it is passed as given. Partial brackets are refused
    (forum, 2026-09-21; lab 2026-10-25)."""
    if not effort or not model or model == "auto":
        return model
    if "[" in model:
        raise ValueError("cursor: put the effort inside the full bracket variant, not in --effort")
    return f"{model}-{effort}"


def b_cursor(s, prompt, model, effort, session, cwd, opts=None):
    m = cursor_model(model, effort)
    # Headless, cursor-agent refuses an untrusted folder; --trust marks it trusted for good.
    argv = [s["bin"], "-p", prompt, "--output-format", "json", "--mode", "ask", "--trust"]
    argv += ["--model", m] if m else []
    argv += ["--resume", session] if session else []
    return argv, {}, None


def b_muse(s, prompt, model, effort, session, cwd, opts=None):
    preset = None if session else str(uuid.uuid4())
    argv = [s["bin"], "exec", "--json", "--session-id", session or preset]
    argv += ["--model", model] if model else []
    argv += ["--reasoning-effort", effort] if effort else []
    return argv + [prompt], {}, preset


def b_kimi(s, prompt, model, effort, session, cwd, opts=None):
    argv = [s["bin"], "-p", prompt, "--output-format", "stream-json"]
    argv += ["-m", model] if model else []
    argv += ["-S", session] if session else []
    return argv, {}, None


# vendor: whose models it serves by default, to refuse routing a host to itself.
# tiers: name -> (model, effort); None means the CLI's own default.
# efforts: what the effort argument accepts (models may accept fewer).
# read_only: what keeps the worker from writing.
SPECS = {
    "claude": dict(web=True, native_schema=True, vendor="anthropic", bins=("claude",), build=b_claude, parse=p_claude,
                   tiers={"cheap": ("haiku", "low"), "mid": ("sonnet", "medium"), "top": ("opus", "high")},
                   efforts=("low", "medium", "high", "xhigh", "max"),
                   read_only="--tools Read,Grep,Glob and --permission-mode plan"),
    "agy": dict(web=True, native_schema=True, vendor="google", bins=("agy",), build=b_agy, parse=p_agy,
                tiers={"cheap": ("gemini-3.8-flash", "low"), "mid": ("gemini-4-argon", "medium"),
                       "top": ("gemini-4-argon", "high")},
                efforts=("low", "medium", "high"),
                pools={"google": ("gemini-",), "claude": ("claude-",)},
                read_only="--mode plan"),
    "opencode": dict(web=True, native_schema=False, vendor="opencode", bins=("opencode", "~/.opencode/bin/opencode"),
                     build=b_opencode, parse=p_opencode,
                     # top is the 1M-context
                     # Nemotron, whose prompts NVIDIA logs: never for private material.
                     tiers={"cheap": ("opencode/deepseek-v4.1-flash-free", None),
                            "mid": ("opencode/glm-5.3-flash-free", None),
                            "top": ("opencode/nemotron-3.5-super-vl-free", None)},
                     efforts=EFFORTS, models=OPENCODE_MODELS,
                     read_only="OPENCODE_CONFIG_CONTENT denies edit, bash, execute, task"),
    "grok": dict(web=True, native_schema=True, vendor="xai", bins=("grok",), build=b_grok, parse=p_grok,
                 # The user's choice (2026-10-26): Grok runs as grok-4.7 at xhigh, never a fast
                 # variant; --effort lowers it. Its 500k window comes from ~/.grok/config.toml.
                 tiers={t: ("grok-4.7", "xhigh") for t in TIERS},
                 efforts=("low", "medium", "high", "xhigh"),
                 read_only="--permission-mode plan, no MCP, no subagents"),
    "codex": dict(web=True, native_schema=False, vendor="openai", bins=("codex",), build=b_codex, parse=p_codex,
                  tiers={"cheap": ("gpt-6-luna", "low"), "mid": ("gpt-reserve", "medium"),
                         "top": ("gpt-reserve", "xhigh")},
                  efforts=("low", "medium", "high", "xhigh", "max", "ultra"),
                  read_only="sandbox_mode read-only, on every turn"),
    "hermes": dict(web=True, native_schema=False, vendor="nous", bins=("hermes",), build=b_hermes, parse=p_hermes,
                   # grok-4.7 at xhigh, as for grok; Hermes reads its 500k window from api.x.ai.
                   tiers={t: ("xai-oauth:grok-4.7", "xhigh") for t in TIERS},
                   efforts=EFFORTS,
                   read_only="-t web,x_search: no file or terminal tools, so put the code in the prompt"),
    "copilot": dict(web=False, native_schema=False, vendor="github", bins=("~/.local/bin/copilot", "copilot"), build=b_copilot,
                    parse=p_copilot, tiers={t: ("auto", None) for t in TIERS},
                    efforts=("none", "minimal", "low", "medium", "high", "xhigh", "max"),
                    read_only="headless denies tools needing approval; write tools excluded"),
    "cursor": dict(web=False, native_schema=False, vendor="cursor", bins=("cursor-agent",), build=b_cursor, parse=p_generic,
                   # Grok 4.7 at xhigh with its 500k window, as a full variant (see cursor_model).
                   tiers={t: ("grok-4.7[context=500k,reasoning_effort=xhigh,fast=false]", None) for t in TIERS}, efforts=EFFORTS,
                   read_only="--mode ask"),
    "muse": dict(web=False, native_schema=False, vendor="muse", bins=("muse",), build=b_muse, parse=p_generic,
                 tiers={"cheap": ("muse-spark-1.3", "low"), "mid": ("muse-spark-1.3", "medium"),
                        "top": ("muse-spark-1.3", "high")},
                 efforts=EFFORTS, read_only="default approval and sandbox (no bypass)"),
    "kimi": dict(web=False, native_schema=False, vendor="moonshot", bins=("kimi", "~/.kimi-code/bin/kimi"), build=b_kimi,
                 parse=p_generic,
                 tiers={"cheap": ("kimi-code/kimi-for-coding-highspeed", None),
                        "mid": ("kimi-code/kimi-for-coding", None), "top": ("kimi-code/k3", None)},
                 efforts=(), read_only=None),
}

# Vendors whose models a host already reaches through its own subagents.
HOST_ENV = {"anthropic": ("CLAUDECODE",)}
MODEL_VENDOR = (("claude-", "anthropic"), ("haiku", "anthropic"), ("sonnet", "anthropic"),
                ("opus", "anthropic"), ("gemini-", "google"), ("gpt-", "openai"), ("grok-", "xai"))


def host_vendors(env=os.environ) -> set:
    return {v for v, keys in HOST_ENV.items() if any(env.get(k) for k in keys)}


def model_vendor(model: str):
    m = (model or "").rpartition(":")[2].rpartition("/")[2].lower()
    return next((v for prefix, v in MODEL_VENDOR if m.startswith(prefix)), None)


def resolve(backend: str, tier: str = "cheap", model=None, effort=None, env=os.environ, web=False) -> dict:
    """Pick binary, model and effort; return them with warnings, or raise ValueError."""
    if backend not in SPECS:
        raise ValueError(f"unknown backend {backend!r}; one of {', '.join(SPECS)}")
    s = dict(SPECS[backend])
    if web and not s["web"]:
        raise ValueError(f"{backend} has no verified web mode; use one of "
                         + ", ".join(b for b, x in SPECS.items() if x["web"]))
    if tier not in TIERS:
        raise ValueError(f"tier must be one of {', '.join(TIERS)}")
    t_model, t_effort = s["tiers"][tier]
    model = model or t_model
    effort = effort if effort is not None else t_effort
    warnings = []
    if effort and effort not in s["efforts"]:
        if not s["efforts"]:
            warnings.append(f"{backend} takes no effort per run; ignored {effort!r} (set it in its config)")
            effort = None
        else:
            raise ValueError(f"{backend} effort must be one of {', '.join(s['efforts'])}")
    if s.get("models") and model not in s["models"]:
        raise ValueError(f"{backend} model must be one of {', '.join(s['models'])}")
    pools = s.get("pools")
    if pools and model:
        pool = next((p for p, prefixes in pools.items() if model.startswith(prefixes)), None)
        if pool and pool != next(iter(pools)):
            warnings.append(f"{model} draws from agy's {pool} quota, which is small; "
                            f"the {next(iter(pools))} pool is the real budget")
    hosts = host_vendors(env)
    if s["vendor"] in hosts:
        raise ValueError(f"the host already reaches {s['vendor']} models through its own "
                         f"subagents; use those, not crew (--allow-same-vendor to override)")
    if model_vendor(model) in hosts:
        warnings.append(f"{model} is the host's own vendor; native subagents would do the same")
    if s["read_only"] is None:
        warnings.append(f"{backend}: no verified read-only headless mode")
    s["bin"] = _bin(*s["bins"])
    if not s["bin"]:
        raise ValueError(f"{backend} CLI not found ({', '.join(s['bins'])})")
    return {"spec": s, "model": model, "effort": effort, "warnings": warnings}


def self_test() -> int:
    n = 0

    def ok(cond, what):
        nonlocal n
        n += 1
        if not cond:
            sys.exit(f"backends self-test failed: {what}")

    ok(p_claude('{"result":"pong","session_id":"s1","is_error":false}')["session"] == "s1", "claude")
    ok(p_claude('{"result":"boom","is_error":true}')["error"] == "boom", "claude error")
    ok(p_agy('{"conversation_id":"c1","status":"SUCCESS","response":"pong\\n"}')["text"] == "pong", "agy")
    ok(p_agy('{"status":"ERROR"}')["error"], "agy error")
    oc = '{"type":"step_start","sessionID":"ses_1"}\n{"type":"text","sessionID":"ses_1","part":{"text":"pong"}}'
    ok(p_opencode(oc) == {"text": "pong", "session": "ses_1", "usage": None, "error": None}, "opencode")
    gk = ('{"type":"assistant","session_id":"g1","message":{"content":[{"type":"text","text":"Checking."}]}}\n'
          '{"type":"assistant","session_id":"g1","message":{"content":[{"type":"text","text":"pong"}]}}\n'
          '{"type":"result","session_id":"g1","is_error":false,"usage":{}}')
    ok(p_grok(gk) == {"text": "pong", "session": "g1", "usage": {}, "error": None}, "grok last message")
    ok(p_grok('{"text":"{\\"a\\":1}","sessionId":"g2","usage":{}}')["text"] == '{"a":1}', "grok schema envelope")
    cx = ('{"type":"thread.started","thread_id":"t1"}\n'
          '{"type":"item.completed","item":{"type":"agent_message","text":"pong"}}\n'
          '{"type":"turn.completed","usage":{"input_tokens":1}}')
    ok(p_codex(cx)["text"] == "pong" and p_codex(cx)["session"] == "t1", "codex")
    hm = '{"type":"text","text":"pong"}\n{"type":"result","text":"pong","session_id":"h1","exit_code":0}'
    ok(p_hermes(hm)["session"] == "h1", "hermes")
    hv = b_hermes(dict(bin="/x"), "q", "xai-oauth:grok-4.7", "low", None, "/r")[0]
    ok(hv[hv.index("-t") + 1] == "web,x_search", "hermes reads the web and X only")
    cp = ('{"type":"assistant.message","data":{"content":"pong"}}\n'
          '{"type":"session.usage_checkpoint","data":{"totalNanoAiu":176373000}}\n'
          '{"type":"result","sessionId":"c1","exitCode":0,"usage":{"premiumRequests":1}}')
    r = p_copilot(cp)
    ok(r["text"] == "pong" and r["session"] == "c1" and not r["error"]
       and r["usage"] == {"premiumRequests": 1, "ai_credits": 0.176373}, "copilot")
    ok(p_copilot('{"type":"assistant.message","data":{"content":"pong"}}')["error"] == "no result event",
       "copilot cut run")
    ok(p_generic('{"type":"result","result":"pong","session_id":"x"}')["session"] == "x", "generic")

    fake = dict(bin="/x")
    argv, _, preset = b_claude(fake, "q", "haiku", "low", None, "/r")
    ok(preset and argv[argv.index("--session-id") + 1] == preset, "claude presets the session id")
    argv, _, _ = b_claude(fake, "q", None, None, "s1", "/r")
    ok(argv[argv.index("--resume") + 1] == "s1" and "--session-id" not in argv, "claude resumes")
    ok(b_agy(fake, "q", "gemini-3.8-flash", "low", None, "/r")[0][-1] == "gemini-3.8-flash-low",
       "agy puts effort in the slug")
    ok(b_agy(fake, "q", "gemini-3.8-flash-high", "low", None, "/r")[0][-1] == "gemini-3.8-flash-high",
       "agy keeps an explicit level")
    argv, env, _ = b_opencode(fake, "q", OPENCODE_MODELS[0], None, "ses_1", "/r")
    ok(argv[-1] == "q" and "-s" in argv and json.loads(env["OPENCODE_CONFIG_CONTENT"]) == OPENCODE_DENY,
       "opencode")
    argv, _, _ = b_codex(fake, "q", "gpt-6-luna", "low", "t1", "/r")
    ok(argv[:3] == ["/x", "exec", "resume"] and argv[-2:] == ["t1", "q"], "codex resume order")
    ok('sandbox_mode="read-only"' in b_codex(fake, "q", None, None, "t1", "/r")[0], "codex read-only on resume")
    argv, _, _ = b_hermes(fake, "q", "xai-oauth:grok-4.7", "low", None, "/r")
    ok(argv[argv.index("--provider") + 1] == "xai-oauth" and argv[argv.index("-m") + 1] == "grok-4.7",
       "hermes provider:model")
    argv, _, preset = b_copilot(fake, "q", "auto", None, None, "/r")
    ok("--session-id" in argv and "apply_patch" in argv and "--allow-all-tools" not in argv, "copilot")
    ok(b_cursor(fake, "q", "grok-4.7", "xhigh", None, "/r")[0][-1] == "grok-4.7-xhigh", "cursor flat id + effort")
    full = "grok-4.7[context=500k,reasoning_effort=xhigh,fast=false]"
    ok(b_cursor(fake, "q", full, None, None, "/r")[0][-1] == full, "cursor full variant passed as given")
    ok(cursor_model("auto", "high") == "auto", "cursor auto ignores effort")
    try:
        cursor_model(full, "high")
        ok(False, "cursor bracket + effort refused")
    except ValueError:
        pass
    web = {"web": True}
    argv, _, _ = b_claude(fake, "q", None, None, None, "/r", dict(web, schema={"type": "object"}))
    ok(argv[argv.index("--tools") + 1] == "WebSearch,WebFetch" and "--json-schema" in argv, "claude web + schema")
    argv, env, _ = b_grok(fake, "q", None, None, None, "/r", dict(web, schema={"type": "object"}))
    ok(argv[argv.index("--tools") + 1] == GROK_WEB_TOOLS and env["GROK_WEB_FETCH"] == "1"
       and "--json-schema" in argv and "streaming-messages-json" not in argv, "grok web + schema")
    ok(b_codex(fake, "q", None, None, None, "/r", web)[0][:3] == ["/x", "--search", "exec"], "codex --search first")
    with tempfile.TemporaryDirectory() as rd:
        _, env, _ = b_opencode(fake, "q", None, None, None, "/r", dict(web, rundir=rd))
        ok(json.loads(env["OPENCODE_CONFIG_CONTENT"])["permission"]["websearch"] == "allow"
           and json.loads(env["OPENCODE_CONFIG_CONTENT"])["permission"]["bash"] == "deny", "opencode web config")
        ok(env["OPENCODE_CONFIG_DIR"] == os.path.join(rd, "oc-web") and 'set("exa")' in open(
            os.path.join(rd, "oc-web", "plugins", "crew-websearch.js"), encoding="utf-8").read(),
           "opencode web provider plugin")
    ok("OPENCODE_CONFIG_DIR" not in b_opencode(fake, "q", None, None, None, "/r", {})[1], "opencode ask: no plugin")
    argv, _, _ = b_agy(fake, "q", None, None, None, "/r", {"schema_path": "/s.json", "timeout": 300})
    ok(argv[argv.index("--json-schema") + 1] == "/s.json" and "300s" in argv, "agy schema + print timeout")
    try:
        resolve("copilot", web=True, env={})
        ok(False, "copilot web refused")
    except ValueError:
        ok(True, "")

    for b, s in SPECS.items():
        ok(set(s["tiers"]) == set(TIERS), f"{b} defines every tier")
        ok(all(e is None or e in s["efforts"] for _, e in s["tiers"].values()), f"{b} tier efforts valid")
    claude_env = {"CLAUDECODE": "1"}
    try:
        resolve("claude", env=claude_env)
        ok(False, "claude from claude is refused")
    except ValueError:
        ok(True, "")
    try:
        resolve("opencode", model="opencode/other-free", env={})
        ok(False, "opencode outside the allowlist is refused")
    except ValueError:
        ok(True, "")
    ok(model_vendor("xai-oauth:grok-4.7") == "xai" and model_vendor("opencode/x") is None, "model_vendor")
    print(f"backends self-test: {n} checks ok")
    return 0


if __name__ == "__main__":
    if sys.argv[1:] == ["--self-test"]:
        sys.exit(self_test())
    sys.exit(__doc__)
