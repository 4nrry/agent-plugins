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
import uuid

TIERS = ("cheap", "mid", "top")
EFFORTS = ("none", "minimal", "low", "medium", "high", "xhigh", "max", "ultra")

# Versions on which a two-turn ask (new, then resumed) returned the right reply.
LIVE = {"claude": "2.1.307", "agy": "1.4.4", "opencode": "2.1.2", "grok": "1.0.62",
        "codex": "0.163.0", "hermes": "0.22.4"}

OPENCODE_MODELS = ("opencode/minimax-m3.1-flash-free", "opencode/deepseek-v4.1-flash-free",
                   "opencode/glm-5.3-flash-free", "opencode/mimo-v2.6-flash-free",
                   "opencode/nemotron-3.5-lightning-free", "opencode/nemotron-3.5-super-vl-free")
OPENCODE_DENY = {"permission": {"edit": "deny", "bash": "deny", "execute": "deny",
                                "task": "deny", "external_directory": "deny"}}
ASK_RULE = ("You are an isolated, read-only worker answering one question for another agent. "
            "Do not edit files, run commands that change anything, or start subagents.")
COPILOT_READONLY_EXCLUDED = ["bash", "task", "apply_patch", "create", "edit", "str_replace_editor",
                             "write_bash"]
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
            "usage": {"usage": j.get("usage"), "cost_usd": j.get("total_cost_usd")}, "error": err}


def p_agy(out):
    j = _json(out)
    ok = j.get("status") == "SUCCESS"
    return {"text": (j.get("response") or "").strip() or None, "session": j.get("conversation_id"),
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
    text (which also carries what rules in ~/.grok/rules made it say first)."""
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
    text, err = None, None
    for ev in _jsonl(out):
        if ev.get("type") == "assistant.message":
            c = (ev.get("data") or {}).get("content")
            if isinstance(c, str) and c.strip():
                text = c
        elif ev.get("type") == "result" and ev.get("exitCode") not in (0, None):
            err = f"exitCode {ev.get('exitCode')}"
    return {"text": text, "session": None, "usage": None, "error": err}


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

def b_claude(s, prompt, model, effort, session, cwd):
    # Read-only tools and no user settings (plugins, hooks): 2.1.307 measured
    # $0.016 a turn on haiku with both, $0.18 without; the session still logs in.
    argv = [s["bin"], "-p", prompt, "--output-format", "json", "--permission-mode", "plan",
            "--tools", "Read,Grep,Glob", "--setting-sources", "project,local",
            "--strict-mcp-config", "--disable-slash-commands"]
    preset = None
    if session:
        argv += ["--resume", session]
    else:
        preset = str(uuid.uuid4())
        argv += ["--session-id", preset]
    argv += ["--model", model] if model else []
    argv += ["--effort", effort] if effort else []
    return argv, {}, preset


def b_agy(s, prompt, model, effort, session, cwd):
    if model and effort and not model.rsplit("-", 1)[-1] in EFFORTS:
        model = f"{model}-{effort}"
    argv = [s["bin"], "-p", prompt, "--output-format", "json", "--mode", "plan",
            "--disable-slash-commands"]
    argv += ["--model", model] if model else []
    argv += ["--conversation", session] if session else []
    return argv, {}, None


def b_opencode(s, prompt, model, effort, session, cwd):
    m = f"{model}#{effort}" if model and effort else model
    argv = [s["bin"], "run", "--standalone", "--format", "json"]
    argv += ["-m", m] if m else []
    argv += ["-s", session] if session else []
    return argv + [prompt], {"OPENCODE_CONFIG_CONTENT": json.dumps(OPENCODE_DENY)}, None


def b_grok(s, prompt, model, effort, session, cwd):
    argv = [s["bin"], "-p", prompt, "--output-format", "streaming-messages-json",
            "--permission-mode", "plan", "--deny", "mcp__*", "--no-subagents", "--rules", ASK_RULE]
    argv += ["-m", model] if model else []
    argv += ["--reasoning-effort", effort] if effort else []
    argv += ["--resume", session] if session else []
    env = {"GROK_MEMORY": "0", "GROK_CLAUDE_RULES_ENABLED": "0", "GROK_CURSOR_RULES_ENABLED": "0"}
    return argv, env, None


def b_codex(s, prompt, model, effort, session, cwd):
    argv = [s["bin"], "exec"] + (["resume"] if session else [])
    # `exec resume` takes no -s, so the sandbox goes in as config on both turns.
    argv += ["--json", "--skip-git-repo-check", "-c", 'sandbox_mode="read-only"']
    argv += ["-m", model] if model else []
    argv += ["-c", f'model_reasoning_effort="{effort}"'] if effort else []
    argv += [session] if session else []
    return argv + [prompt], {}, None


def b_hermes(s, prompt, model, effort, session, cwd):
    provider, _, m = (model or "").rpartition(":")
    argv = [s["bin"], "chat", "-q", prompt, "-Q", "--format", "stream-json", "-t", "web",
            "--ignore-rules"]
    argv += ["--provider", provider] if provider else []
    argv += ["-m", m] if m else []
    argv += ["--reasoning", effort] if effort else []
    argv += ["--resume", session] if session else []
    return argv, {}, None


def b_copilot(s, prompt, model, effort, session, cwd):
    preset = None if session else str(uuid.uuid4())
    argv = [s["bin"], "-p", prompt, "--output-format", "json", "--max-ai-credits",
            str(COPILOT_MAX_CREDITS), "--excluded-tools", *COPILOT_READONLY_EXCLUDED]
    argv += ["--model", model] if model else []
    argv += ["--reasoning-effort", effort] if effort else []
    argv += ["--resume", session] if session else ["--session-id", preset]
    return argv, {}, preset


def b_cursor(s, prompt, model, effort, session, cwd):
    m = f"{model}[effort={effort}]" if model and effort else model
    argv = [s["bin"], "-p", prompt, "--output-format", "json", "--mode", "ask"]
    argv += ["--model", m] if m else []
    argv += ["--resume", session] if session else []
    return argv, {}, None


def b_muse(s, prompt, model, effort, session, cwd):
    preset = None if session else str(uuid.uuid4())
    argv = [s["bin"], "exec", "--json", "--session-id", session or preset]
    argv += ["--model", model] if model else []
    argv += ["--reasoning-effort", effort] if effort else []
    return argv + [prompt], {}, preset


def b_kimi(s, prompt, model, effort, session, cwd):
    argv = [s["bin"], "-p", prompt, "--output-format", "stream-json"]
    argv += ["-m", model] if model else []
    argv += ["-S", session] if session else []
    return argv, {}, None


# vendor: whose models it serves by default, to refuse routing a host to itself.
# tiers: name -> (model, effort); None means the CLI's own default.
# efforts: what the effort argument accepts (models may accept fewer).
# read_only: what keeps the worker from writing.
SPECS = {
    "claude": dict(vendor="anthropic", bins=("claude",), build=b_claude, parse=p_claude,
                   tiers={"cheap": ("haiku", "low"), "mid": ("sonnet", "medium"), "top": ("opus", "high")},
                   efforts=("low", "medium", "high", "xhigh", "max"),
                   read_only="--tools Read,Grep,Glob and --permission-mode plan"),
    "agy": dict(vendor="google", bins=("agy",), build=b_agy, parse=p_agy,
                tiers={"cheap": ("gemini-3.8-flash", "low"), "mid": ("gemini-4-argon", "medium"),
                       "top": ("gemini-4-argon", "high")},
                efforts=("low", "medium", "high"),
                pools={"google": ("gemini-",), "claude": ("claude-",)},
                read_only="--mode plan"),
    "opencode": dict(vendor="opencode", bins=("opencode", "~/.opencode/bin/opencode"),
                     build=b_opencode, parse=p_opencode,
                     tiers={"cheap": (OPENCODE_MODELS[0], None), "mid": (OPENCODE_MODELS[1], None),
                            "top": (OPENCODE_MODELS[2], None)},
                     efforts=EFFORTS, models=OPENCODE_MODELS,
                     read_only="OPENCODE_CONFIG_CONTENT denies edit, bash, execute, task"),
    "grok": dict(vendor="xai", bins=("grok",), build=b_grok, parse=p_grok,
                 tiers={"cheap": ("grok-4.7-build-fast", "low"), "mid": ("grok-4.7", "medium"),
                        "top": ("grok-4.7", "high")},
                 efforts=("low", "medium", "high", "xhigh"),
                 read_only="--permission-mode plan, no MCP, no subagents"),
    "codex": dict(vendor="openai", bins=("codex",), build=b_codex, parse=p_codex,
                  tiers={"cheap": ("gpt-6-luna", "low"), "mid": ("gpt-reserve", "medium"),
                         "top": ("gpt-reserve", "xhigh")},
                  efforts=("low", "medium", "high", "xhigh", "max", "ultra"),
                  read_only="sandbox_mode read-only, on every turn"),
    "hermes": dict(vendor="nous", bins=("hermes",), build=b_hermes, parse=p_hermes,
                   tiers={"cheap": ("xai-oauth:grok-4.7-build-fast", "low"),
                          "mid": ("xai-oauth:grok-4.7", "medium"), "top": ("xai-oauth:grok-4.7", "high")},
                   efforts=EFFORTS,
                   read_only="-t web: no file or terminal tools, so put the code in the prompt"),
    "copilot": dict(vendor="github", bins=("~/.local/bin/copilot", "copilot"), build=b_copilot,
                    parse=p_copilot, tiers={t: ("auto", None) for t in TIERS},
                    efforts=("none", "minimal", "low", "medium", "high", "xhigh", "max"),
                    read_only="headless denies tools needing approval; write tools excluded"),
    "cursor": dict(vendor="cursor", bins=("cursor-agent",), build=b_cursor, parse=p_generic,
                   tiers={t: ("auto", None) for t in TIERS}, efforts=EFFORTS,
                   read_only="--mode ask"),
    "muse": dict(vendor="muse", bins=("muse",), build=b_muse, parse=p_generic,
                 tiers={"cheap": ("muse-spark-1.3", "low"), "mid": ("muse-spark-1.3", "medium"),
                        "top": ("muse-spark-1.3", "high")},
                 efforts=EFFORTS, read_only="default approval and sandbox (no bypass)"),
    "kimi": dict(vendor="moonshot", bins=("kimi", "~/.kimi-code/bin/kimi"), build=b_kimi,
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


def resolve(backend: str, tier: str = "cheap", model=None, effort=None, env=os.environ) -> dict:
    """Pick binary, model and effort; return them with warnings, or raise ValueError."""
    if backend not in SPECS:
        raise ValueError(f"unknown backend {backend!r}; one of {', '.join(SPECS)}")
    s = dict(SPECS[backend])
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
    cx = ('{"type":"thread.started","thread_id":"t1"}\n'
          '{"type":"item.completed","item":{"type":"agent_message","text":"pong"}}\n'
          '{"type":"turn.completed","usage":{"input_tokens":1}}')
    ok(p_codex(cx)["text"] == "pong" and p_codex(cx)["session"] == "t1", "codex")
    hm = '{"type":"text","text":"pong"}\n{"type":"result","text":"pong","session_id":"h1","exit_code":0}'
    ok(p_hermes(hm)["session"] == "h1", "hermes")
    cp = '{"type":"assistant.message","data":{"content":"pong"}}\n{"type":"result","exitCode":0}'
    ok(p_copilot(cp)["text"] == "pong" and not p_copilot(cp)["error"], "copilot")
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
    ok(b_cursor(fake, "q", "gpt-5.2", "high", None, "/r")[0][-1] == "gpt-5.2[effort=high]", "cursor")

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
