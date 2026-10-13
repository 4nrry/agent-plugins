#!/usr/bin/env python3
"""agy-worker: run Google's Antigravity CLI (`agy`) headless as a guarded worker.

Claude plans and reviews; agy executes one well-scoped slice. This script is
the guard rail between them. Subcommands:

  delegate TASK.json   run the task under agy with guard hooks and a gate
  review [PROMPT...]   read-only second opinion (--mode plan + --json-schema)
  gate TASK.json       run the task's gate by hand (--baseline: commands only)
  hook pre|stop|start  agy workspace hook handlers (installed per run)
  --self-test          exercises everything that does not need agy itself

Why each check exists is in the plugin README; the short version is that agy
1.3.4 reports success in most of the ways it fails (measured, n=1 each):
timeouts, denied actions and an unsatisfied --json-schema all exit 0, a
PreToolUse hook printing `{}` denies the call, and --sandbox confines nothing.
So nothing here trusts the exit code, and every hook prints an explicit
decision even when it crashes.

Stdlib only. State lives in `$(git rev-parse --git-path agy-worker)`, so a run
never dirties the work tree; the only file written into the tree is
`.agents/hooks.json`, for the duration of the run, and it is removed after.
"""

import argparse
import fnmatch
import hashlib
import json
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time

HOOK_FILE = ".agents/hooks.json"
STATE_NAME = "agy-worker"
DEFAULT_MODEL = "gemini-3.8-flash-high"
DEFAULT_TIMEOUT = "30m"
DEFAULT_REVIEW_TIMEOUT = "15m"
DEFAULT_GATE_TIMEOUT = 900
DEFAULT_MAX_GATE_ATTEMPTS = 5
DEFAULT_MIN_QUOTA = 0.05
MAX_PROMPT_BYTES = 100_000          # one argv string is capped at 128 KiB on Linux
MAX_DIFF_BYTES = 60_000
TAIL_CHARS = 6000
TIMEOUT_MARKER = "[agy] print timeout"
AUTO_DENY_MARKER = "auto-denied"
NO_OUTPUT_MARKER = "run ended with no output"

# The structured-output tool: --json-schema is implemented as a `finish` tool
# whose parameters are the schema (seen in the lab: "The `finish` tool cannot
# be executed because its validation schema..."). Its args are the report, so
# the path guard must not scan them, and it is where the gate can refuse "done".
FINISH_TOOLS = {"finish"}
GATE_STOP_REASONS = {"NO_TOOL_CALL", "TERMINAL_STEP_TYPE"}

# Arguments that carry file *content* or prose, not paths to touch.
CONTENT_KEYS = {"CodeContent", "ReplacementContent", "TargetContent",
                "ReplacementChunks", "Instruction", "Description", "toolSummary",
                "toolAction", "Query", "Content", "Message", "Summary"}

# Tools whose effects the hooks cannot see or bound (subagents may not carry
# workspace hooks; schedules outlive the run; images cost quota).
DENY_TOOLS = re.compile(r"^(invoke_subagent|define_subagent|manage_subagents|"
                        r"schedule|generate_image|browser_.*)$")

SYSTEM_PATHS = ("/dev/null", "/dev/stdout", "/dev/stderr", "/usr/bin",
                "/bin", "/usr/local/bin")

DENY_COMMANDS = [
    (r"\bgit\s+(-C\s+\S+\s+)?(push|commit|reset|clean|stash|checkout|restore|"
     r"rebase|merge|switch|cherry-pick|revert|am|apply|tag|worktree|config|"
     r"update-ref|filter-branch|branch\s+-[dDmM])\b", "git que altera historico, arvore ou config"),
    (r"\brm\s+(-[a-zA-Z]*[rR]|--recursive)", "rm recursivo"),
    (r"\b(npm|pnpm|yarn|bun)\s+(install|i|ci|add|remove|rm|uninstall|update|"
     r"upgrade|up|link|publish)\b", "install ou publish de pacote"),
    (r"\b(pip3?|poetry|cargo|gem|composer)\s+(install|add|remove|uninstall|publish)\b"
     r"|\bgo\s+(get|install)\b|\buv\s+(add|remove|sync|pip\s+install)\b",
     "install de pacote"),
    (r"\b(apt|apt-get|dnf|yum|pacman|brew|snap|flatpak)\b", "gerenciador de pacotes do sistema"),
    (r"\b(npx|bunx)\s+(-y|--yes)\b|\bpnpm\s+dlx\b", "execucao de pacote baixado"),
    (r"(^|[\s;|&(])(sudo|su|doas)(\s|$)", "elevacao de privilegio"),
    (r"\b(deploy|publish)\b", "deploy ou publish"),
    (r"\b(wrangler|vercel|netlify|firebase|flyctl|heroku|kubectl|helm|terraform|"
     r"pulumi|docker|podman|gcloud|aws|az)\b", "infra, deploy ou container"),
    (r"\b(prisma|drizzle-kit|knex|sequelize|alembic|typeorm)\b.*\b(migrate|push|reset|seed)\b"
     r"|\bdb:(migrate|push|reset|seed|drop)\b|\bmanage\.py\s+migrate\b",
     "migracao ou escrita de banco"),
    (r"\b(psql|mysql|sqlite3|mongosh|redis-cli)\b", "cliente de banco"),
    (r"\bsed\b[^|;&]*\s(-[a-zA-Z]*i|--in-place)|\bperl\s+-[a-zA-Z]*i|\btee\b|(^|[\s;|&])dd\s",
     "edicao de arquivo pelo shell"),
    (r"\b(curl|wget|ssh|scp|rsync|nc|ncat|telnet|ftp)\b", "rede"),
    (r"(^|[\s;|&(])(ps|pgrep|pkill|kill|killall|top|htop|lsof)(\s|$)|/proc\b",
     "inspecao de processos"),
    (r"(^|[\s=:'\"(/])\.\.(/|\s|$)", "caminho com .."),
    (r"\$\{?HOME\b|\bprintenv\b|(^|[\s;|&])env\s*($|[;|&])", "home ou ambiente do usuario"),
]

DEFAULT_REPORT_SCHEMA = {
    "type": "object",
    "required": ["status", "files_changed", "checks_run", "divergences",
                 "out_of_scope_needs"],
    "properties": {
        "status": {"type": "string", "enum": ["done", "partial", "blocked"]},
        "files_changed": {"type": "array", "items": {"type": "string"}},
        "checks_run": {"type": "array", "items": {"type": "string"},
                       "description": "each command you ran, suffixed with PASS or FAIL as you saw it"},
        "divergences": {"type": "array", "items": {"type": "string"},
                        "description": "every behaviour difference you introduced versus the source of truth, with the reason; empty only if none"},
        "out_of_scope_needs": {"type": "array", "items": {"type": "string"},
                               "description": "files outside the allowed list that would need to change, and why"},
        "notes": {"type": "string"},
    },
}

DEFAULT_REVIEW_SCHEMA = {
    "type": "object",
    "required": ["verdict", "findings", "summary"],
    "properties": {
        "verdict": {"type": "string", "enum": ["approve", "request_changes", "unsure"]},
        "findings": {"type": "array", "items": {
            "type": "object",
            "required": ["file", "severity", "claim", "evidence"],
            "properties": {
                "file": {"type": "string"},
                "line": {"type": "integer"},
                "severity": {"type": "string", "enum": ["high", "medium", "low"]},
                "claim": {"type": "string"},
                "evidence": {"type": "string",
                             "description": "the exact code or text that supports the claim"},
            }}},
        "summary": {"type": "string"},
    },
}


class Refusal(Exception):
    """A precondition failed before agy was started. Nothing ran."""


# --------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------

def eprint(*a) -> None:
    print(*a, file=sys.stderr, flush=True)


def git(repo: str, *args: str, check: bool = True, binary: bool = False):
    proc = subprocess.run(["git", "-C", repo, "-c", "color.ui=false", *args],
                          capture_output=True, text=not binary)
    if check and proc.returncode != 0:
        err = proc.stderr if not binary else proc.stderr.decode(errors="replace")
        raise Refusal(f"git {' '.join(args)} falhou: {err.strip()}")
    return proc.stdout


def repo_root(start: str) -> str:
    try:
        out = git(start, "rev-parse", "--show-toplevel")
    except (Refusal, FileNotFoundError, NotADirectoryError) as exc:
        raise Refusal(f"{start} nao e um repositorio git: {exc}") from exc
    return os.path.realpath(out.strip())


def state_base(repo: str) -> str:
    return git(repo, "rev-parse", "--path-format=absolute", "--git-path", STATE_NAME).strip()


def parse_duration(text) -> int:
    if isinstance(text, (int, float)):
        return int(text)
    m = re.fullmatch(r"\s*(\d+)\s*([smh]?)\s*", str(text))
    if not m:
        raise Refusal(f"duracao invalida: {text!r} (use 90s, 20m, 1h)")
    n, unit = int(m.group(1)), m.group(2) or "s"
    return n * {"s": 1, "m": 60, "h": 3600}[unit]


def tail(text: str, n: int = TAIL_CHARS) -> str:
    return text if len(text) <= n else "…(cortado)…\n" + text[-n:]


def in_globs(rel: str, globs) -> bool:
    """Bash-pattern semantics as in the prototype: `*` crosses `/`."""
    return any(fnmatch.fnmatchcase(rel, g) for g in globs if g and not g.startswith("#"))


def append_jsonl(path: str, obj: dict) -> None:
    obj = {"t": time.strftime("%H:%M:%S"), **obj}
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(obj, ensure_ascii=False) + "\n")


def read_json(path: str, default=None):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


def write_json(path: str, obj) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


# --------------------------------------------------------------------------
# task file
# --------------------------------------------------------------------------

def load_task(path: str) -> dict:
    path = os.path.abspath(path)
    task = read_json(path)
    if not isinstance(task, dict):
        raise Refusal(f"{path}: nao e um objeto JSON legivel")
    base = os.path.dirname(path)
    if "prompt_file" in task:
        pf = os.path.join(base, task["prompt_file"])
        try:
            with open(pf, encoding="utf-8") as fh:
                task["prompt"] = fh.read()
        except OSError as exc:
            raise Refusal(f"prompt_file {pf}: {exc}") from exc
    if isinstance(task.get("report_schema"), str):
        sp = os.path.join(base, task["report_schema"])
        task["report_schema"] = read_json(sp)
        if task["report_schema"] is None:
            raise Refusal(f"report_schema {sp}: nao parseia")
    return normalize_task(task)


def normalize_task(task: dict) -> dict:
    errs = []
    prompt = task.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        errs.append("prompt (ou prompt_file) ausente")
    elif len(prompt.encode()) > MAX_PROMPT_BYTES:
        errs.append(f"prompt maior que {MAX_PROMPT_BYTES} bytes; aponte para arquivos em vez de cola-los")
    scope = task.get("scope")
    if not (isinstance(scope, list) and scope and all(isinstance(s, str) and s for s in scope)):
        errs.append("scope deve ser uma lista nao vazia de globs relativos a raiz do repo")
    elif any(s.startswith("/") or ".." in s.split("/") for s in scope):
        errs.append("scope: globs sao relativos a raiz do repo, sem / inicial e sem ..")
    gate = task.get("gate")
    if not isinstance(gate, dict):
        errs.append("gate deve ser um objeto {format, checks, forbid}")
        gate = {}
    for key in ("format", "checks", "forbid"):
        val = gate.get(key, [])
        if not (isinstance(val, list) and all(isinstance(x, str) for x in val)):
            errs.append(f"gate.{key} deve ser lista de strings")
    if not gate.get("checks") and not gate.get("format"):
        errs.append("gate sem nenhum comando: sem checks o gate so confere escopo, e isso nao prova nada")
    for pat in gate.get("forbid", []) or []:
        try:
            re.compile(pat)
        except re.error as exc:
            errs.append(f"gate.forbid {pat!r}: regex invalida ({exc})")
    schema = task.get("report_schema", DEFAULT_REPORT_SCHEMA)
    if not (isinstance(schema, dict) and schema.get("type") == "object"):
        errs.append("report_schema precisa de raiz \"type\": \"object\" (agy 1.2.14+ recusa outra raiz)")
    for key in ("side_effects", "allow_paths", "deny_commands"):
        val = task.get(key, [])
        if not (isinstance(val, list) and all(isinstance(x, str) for x in val)):
            errs.append(f"{key} deve ser lista de strings")
    for pat in task.get("deny_commands", []) or []:
        try:
            re.compile(pat)
        except re.error as exc:
            errs.append(f"deny_commands {pat!r}: regex invalida ({exc})")
    try:
        parse_duration(task.get("timeout", DEFAULT_TIMEOUT))
        parse_duration(task.get("gate_timeout", DEFAULT_GATE_TIMEOUT))
    except Refusal as exc:
        errs.append(str(exc))
    if errs:
        raise Refusal("task invalida:\n  - " + "\n  - ".join(errs))
    return {
        "prompt": prompt,
        "scope": list(scope),
        "gate": {"format": list(gate.get("format", [])), "checks": list(gate.get("checks", [])),
                 "forbid": list(gate.get("forbid", []))},
        "report_schema": schema,
        "model": task.get("model", DEFAULT_MODEL),
        "timeout": parse_duration(task.get("timeout", DEFAULT_TIMEOUT)),
        "gate_timeout": parse_duration(task.get("gate_timeout", DEFAULT_GATE_TIMEOUT)),
        "max_gate_attempts": int(task.get("max_gate_attempts", DEFAULT_MAX_GATE_ATTEMPTS)),
        "side_effects": list(task.get("side_effects", [])),
        "allow_paths": list(task.get("allow_paths", [])),
        "deny_commands": list(task.get("deny_commands", [])),
        "min_quota": float(task.get("min_quota", DEFAULT_MIN_QUOTA)),
    }


def compose_prompt(task: dict, repo: str) -> str:
    g = task["gate"]
    lst = lambda xs: ", ".join(f"`{x}`" for x in xs) if xs else "(none)"  # noqa: E731
    steps = ["only allowed files changed, and at least one"]
    if g["forbid"]:
        steps.append(f"no added line matches any of: {lst(g['forbid'])}")
    if g["format"]:
        steps.append(f"format check: {lst(g['format'])}")
    if g["checks"]:
        steps.append(f"checks: {lst(g['checks'])}")
    steps_txt = "\n".join(f"  {i}. {s}" for i, s in enumerate(steps, 1))
    note = "`{files}` stands for the allowed files you changed. " if any(
        "{files}" in c for c in g["format"] + g["checks"]) else ""
    side = (f"- These files may be changed by tools as a side effect: {lst(task['side_effects'])}. "
            "Do not edit or revert them.\n") if task["side_effects"] else ""
    return f"""{task['prompt'].rstrip()}

---
## Operating rules (enforced by hooks; not negotiable)
- Repository root: `{repo}`. Work only inside it. Absolute paths outside it, `~`, `$HOME` and `..` are blocked.
- You may create or edit ONLY files matching: {lst(task['scope'])}. Use the file-editing tools; never write files through the shell.
- Never run: git commit/push/checkout/reset/stash, package installs, deploys, migrations, network tools, or process inspection (ps, kill).
{side}- If a file outside the allowed list must change, do NOT work around it and do not fix unrelated things: say so in the report (`out_of_scope_needs`).
- When you declare the task done, this gate runs; if any step fails you will be shown its output and must continue:
{steps_txt}
  {note}Run the format and check commands yourself before declaring done. The gate is fully described here; do not search the filesystem for it.
- Final report: fill every field of the required schema. List every behaviour divergence you introduced and why. Do not claim a check passed unless you saw it pass.
"""


# --------------------------------------------------------------------------
# PreToolUse guard (pure)
# --------------------------------------------------------------------------

PATH_TOKEN = re.compile(r"""(?:^|[\s=:"'(,\[])(~[A-Za-z0-9._/+@-]*|/[A-Za-z0-9._~/+@-]*)""")


def path_tokens(args: dict):
    def strings(v):
        if isinstance(v, str):
            yield v
        elif isinstance(v, dict):
            for k, x in v.items():
                if k not in CONTENT_KEYS:
                    yield from strings(x)
        elif isinstance(v, list):
            for x in v:
                yield from strings(x)
    for s in strings({k: v for k, v in args.items() if k not in CONTENT_KEYS}):
        for m in PATH_TOKEN.finditer(s):
            tok = m.group(1)
            if tok == "~" or tok.startswith("~/"):
                yield tok
            elif len(tok) > 1 and (tok[1].isalnum() or tok[1] == "."):
                yield tok


def path_allowed(tok: str, repo: str, extra) -> bool:
    if tok == "~" or tok.startswith("~/"):
        tok = os.path.expanduser(tok)
    p = os.path.normpath(tok)
    for base in (repo, *SYSTEM_PATHS, *extra):
        base = os.path.normpath(os.path.expanduser(base))
        if p == base or p.startswith(base.rstrip("/") + "/"):
            return True
    return False


def is_gate_command(cmd: str, gate_cmds) -> bool:
    """The worker is told to run the gate itself, so a gate command is never
    blocked by the generic deny list -- but only the command itself: anything
    chained after it (`npm test && git commit`) goes through the full check."""
    cmd = cmd.strip()
    for gc in gate_cmds:
        prefix = gc.split("{files}")[0].strip()
        if prefix and cmd.startswith(prefix) and not re.search(r"[;&|`]|\$\(", cmd[len(prefix):]):
            return True
    return False


def decide_pre(payload: dict, ctx: dict) -> dict:
    """Decision for every tool call except the gate on `finish`. Always explicit."""
    call = payload.get("toolCall") or {}
    name = call.get("name", "")
    args = call.get("args") or {}
    if not isinstance(args, dict):
        args = {}
    repo = ctx["repo"]
    if name in FINISH_TOOLS:
        return {"decision": "allow"}
    if DENY_TOOLS.match(name):
        return {"decision": "deny", "reason": f"Ferramenta {name} bloqueada neste worker: "
                "o efeito dela escapa aos guard rails. Faca o trabalho voce mesmo, dentro do escopo."}
    for tok in path_tokens(args):
        if not path_allowed(tok, repo, ctx.get("allow_paths", [])):
            return {"decision": "deny", "reason": f"Acesso fora do repositorio bloqueado: {tok}. "
                    f"Trabalhe so dentro de {repo}. O gate esta descrito no enunciado; nao procure por ele."}
    target = args.get("TargetFile")
    if isinstance(target, str) and target:
        abs_t = os.path.normpath(target if os.path.isabs(target) else os.path.join(repo, target))
        rel = os.path.relpath(abs_t, repo)
        if rel.startswith("..") or rel.split("/")[0] in (".git", ".agents"):
            return {"decision": "deny", "reason": f"Escrita fora da area de trabalho: {target}."}
        if not in_globs(rel, ctx.get("scope", [])):
            allowed = " ".join(ctx.get("scope", [])) or "(nenhum: modo somente leitura)"
            return {"decision": "deny", "reason": f"Fora do escopo desta tarefa: {rel}. Permitidos: "
                    f"{allowed}. Nao contorne pelo shell; se outro arquivo precisar mudar, diga no relatorio "
                    "(out_of_scope_needs)."}
    cmd = args.get("CommandLine")
    if isinstance(cmd, str) and cmd.strip():
        if not is_gate_command(cmd, ctx.get("gate_commands", [])):
            for pat, label in ctx.get("deny_patterns", []):
                if re.search(pat, cmd):
                    return {"decision": "deny", "reason": f"Comando bloqueado ({label}): {cmd!r}. "
                            "Edite so com as ferramentas de edicao; sem commit, push, install, deploy, "
                            "migracao, rede ou processos. Testes, lint, typecheck e leitura sao permitidos."}
    return {"decision": "allow"}


# --------------------------------------------------------------------------
# tree inspection and the gate
# --------------------------------------------------------------------------

def changed_paths(repo: str) -> list:
    out = git(repo, "status", "--porcelain=v1", "-z", "--untracked-files=all")
    recs = out.split("\0")
    paths, i = [], 0
    while i < len(recs):
        rec = recs[i]
        i += 1
        if len(rec) < 4:
            continue
        xy, path = rec[:2], rec[3:]
        paths.append(path)
        if "R" in xy or "C" in xy:          # rename/copy: next record is the source
            if i < len(recs) and recs[i]:
                paths.append(recs[i])
            i += 1
    return [p for p in dict.fromkeys(paths) if p != HOOK_FILE]


def classify(paths, scope, side_effects) -> dict:
    out = {"in_scope": [], "side_effects": [], "out_of_scope": []}
    for p in paths:
        if in_globs(p, scope):
            out["in_scope"].append(p)
        elif in_globs(p, side_effects):
            out["side_effects"].append(p)
        else:
            out["out_of_scope"].append(p)
    return out


def fingerprint(repo: str, side_effects) -> str:
    h = hashlib.sha256()
    tracked = set(git(repo, "ls-files", "-z").split("\0"))
    for p in sorted(changed_paths(repo)):
        if in_globs(p, side_effects):
            continue
        h.update(p.encode() + b"\0")
        if p in tracked:
            h.update(git(repo, "diff", "HEAD", "--binary", "--", p, binary=True))
        else:
            try:
                with open(os.path.join(repo, p), "rb") as fh:
                    h.update(fh.read())
            except OSError:
                h.update(b"<missing>")
    return h.hexdigest()


def added_lines(repo: str, path: str, tracked: set):
    """(line_no, text) for each line the change adds to `path`."""
    full = os.path.join(repo, path)
    if path not in tracked:
        try:
            with open(full, encoding="utf-8", errors="replace") as fh:
                for n, line in enumerate(fh, 1):
                    yield n, line.rstrip("\n")
        except OSError:
            return
        return
    n = 0
    for line in git(repo, "diff", "HEAD", "-U0", "--", path).splitlines():
        m = re.match(r"^@@ -\S+ \+(\d+)", line)
        if m:
            n = int(m.group(1))
        elif line.startswith("+") and not line.startswith("+++"):
            yield n, line[1:]
            n += 1


def run_gate(repo: str, ctx: dict, baseline: bool = False):
    """Returns (passed, text, classification)."""
    lines, ok = [], True
    say = lines.append
    cls = classify(changed_paths(repo), ctx["scope"], ctx.get("side_effects", []))
    files = [f for f in cls["in_scope"] if os.path.exists(os.path.join(repo, f))]
    if not baseline:
        for p in cls["out_of_scope"]:
            say(f"GATE: alterado fora do escopo: {p} (reverta; se precisava mudar, diga no relatorio)")
            ok = False
        if not cls["in_scope"]:
            say("GATE: nenhum arquivo do escopo foi alterado")
            ok = False
        if ctx["gate"]["forbid"] and files:
            tracked = set(git(repo, "ls-files", "-z").split("\0"))
            for f in files:
                for n, text in added_lines(repo, f, tracked):
                    for pat in ctx["gate"]["forbid"]:
                        if re.search(pat, text):
                            say(f"GATE: atalho proibido /{pat}/ em {f}:{n}: {text.strip()[:160]}")
                            ok = False
    quoted = " ".join(shlex.quote(f) for f in files)
    for kind in ("format", "checks"):
        for cmd in ctx["gate"][kind]:
            if "{files}" in cmd:
                if not files:
                    say(f"GATE: [{kind}] {cmd}: pulado, nenhum arquivo do escopo")
                    continue
                cmd = cmd.replace("{files}", quoted)
            try:
                # AGY_WORKER_GATE lets a command tell the gate run from the
                # worker's own run of the same command.
                proc = subprocess.run(["bash", "-c", cmd], cwd=repo, capture_output=True,
                                      text=True, timeout=ctx.get("gate_timeout", DEFAULT_GATE_TIMEOUT),
                                      env={**os.environ, "AGY_WORKER_GATE": "1"})
                rc, out = proc.returncode, (proc.stdout + proc.stderr)
            except subprocess.TimeoutExpired as exc:
                rc = "timeout"
                out = ((exc.stdout or b"").decode(errors="replace") if isinstance(exc.stdout, bytes)
                       else (exc.stdout or ""))
            if rc == 0:
                say(f"GATE: [{kind}] {cmd}: ok")
            else:
                ok = False
                say(f"GATE: [{kind}] {cmd}: FALHOU (rc={rc})")
                say(tail(out.strip(), 3000))
    say("GATE: PASS" if ok else "GATE: FAIL")
    return ok, "\n".join(lines), cls


def gate_cached(rundir: str, ctx: dict, trigger: str):
    """Gate with a per-tree-state cache of PASSES, counted against max_gate_attempts.

    The same gate is asked for twice for one state (the `finish` tool, then
    Stop with TERMINAL_STEP_TYPE); re-running an `nx test` for an identical
    tree only burns time. Failures are never cached: in the lab a cached
    failure left the worker nothing legitimate to change, and it went looking
    for the gate (`env`, `git config --list`, /proc). A flaky check must get
    its re-run.
    """
    repo = ctx["repo"]
    st_path = os.path.join(rundir, "gate-state.json")
    st = read_json(st_path, {"attempts": 0, "runs": 0})
    st["attempts"] += 1
    fp = fingerprint(repo, ctx.get("side_effects", []))
    if st.get("fingerprint") == fp and st.get("passed") is True:
        passed, text, cached = True, st["text"], True
    else:
        passed, text, _ = run_gate(repo, ctx)
        st["runs"] += 1
        with open(os.path.join(rundir, f"gate-{st['runs']}.log"), "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
        # Gate commands can themselves touch the tree (formatters, Nx config);
        # the cache key is the state *after* them, so an identical re-check hits.
        fp = fingerprint(repo, ctx.get("side_effects", []))
        st.update(fingerprint=fp, passed=passed, text=text)
        cached = False
    write_json(st_path, st)
    append_jsonl(os.path.join(rundir, "guard.jsonl"),
                 {"event": "gate", "trigger": trigger, "attempt": st["attempts"],
                  "passed": passed, "cached": cached})
    return passed, text, st["attempts"]


# --------------------------------------------------------------------------
# hook entry points (run by agy, one process per event)
# --------------------------------------------------------------------------

def load_ctx(rundir: str) -> dict:
    ctx = read_json(os.path.join(rundir, "ctx.json"))
    if not isinstance(ctx, dict):
        raise RuntimeError(f"ctx.json ilegivel em {rundir}")
    ctx["deny_patterns"] = [tuple(x) for x in ctx.get("deny_patterns", [])]
    return ctx


def hook_main(event: str, rundir: str) -> int:
    raw = sys.stdin.read()
    log = os.path.join(rundir, "guard.jsonl")
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except ValueError:
        payload = {}
    try:
        ctx = load_ctx(rundir)
        if event == "start":
            append_jsonl(log, {"event": "session_start", "model": payload.get("modelName"),
                               "conversation": payload.get("conversationId")})
            out = {}
        elif event == "pre":
            name = (payload.get("toolCall") or {}).get("name", "")
            if name in FINISH_TOOLS and ctx.get("mode") == "delegate":
                passed, text, n = gate_cached(rundir, ctx, "finish")
                if passed or n >= ctx["max_gate_attempts"]:
                    out = {"decision": "allow"}
                else:
                    out = {"decision": "deny", "reason":
                           f"O gate FALHOU (tentativa {n} de {ctx['max_gate_attempts']}); a tarefa nao "
                           "esta pronta. Corrija a causa real, sem desativar teste nem sair do escopo, e "
                           f"so entao chame finish de novo. Saida do gate:\n{tail(text)}"}
            else:
                out = decide_pre(payload, ctx)
            entry = {"event": "pre", "tool": name, "decision": out["decision"]}
            if out["decision"] != "allow":
                entry["reason"] = out.get("reason", "")[:300]
                entry["args"] = {k: (v if len(str(v)) < 300 else str(v)[:300] + "…")
                                 for k, v in ((payload.get("toolCall") or {}).get("args") or {}).items()
                                 if k not in CONTENT_KEYS}
            append_jsonl(log, entry)
        elif event == "stop":
            reason = payload.get("terminationReason", "")
            if ctx.get("mode") != "delegate" or reason not in GATE_STOP_REASONS:
                append_jsonl(log, {"event": "stop", "reason": reason, "error": payload.get("error")})
                out = {"decision": "stop"}
            else:
                passed, text, n = gate_cached(rundir, ctx, f"stop:{reason}")
                if passed or n >= ctx["max_gate_attempts"]:
                    out = {"decision": "stop"}
                else:
                    out = {"decision": "continue", "reason":
                           f"Voce declarou terminado, mas o gate FALHOU (tentativa {n} de "
                           f"{ctx['max_gate_attempts']}). Corrija a causa real, sem desativar teste, "
                           f"sem atalho proibido e sem sair do escopo. Saida do gate:\n{tail(text)}"}
                append_jsonl(log, {"event": "stop", "reason": reason, "decision": out["decision"]})
        else:
            out = {}
    except Exception as exc:  # noqa: BLE001 — a crashing guard must still decide
        try:
            append_jsonl(log, {"event": f"{event}_error", "error": repr(exc)[:500]})
        except OSError:
            pass
        out = ({"decision": "deny", "reason": f"guard interno falhou ({exc!r}); chamada negada por seguranca"}
               if event == "pre" else {"decision": "stop"} if event == "stop" else {})
    print(json.dumps(out, ensure_ascii=False))
    return 0


# --------------------------------------------------------------------------
# agy invocation and result evaluation
# --------------------------------------------------------------------------

def parse_models(text: str) -> list:
    return [ln.split("\t", 1)[0].strip() for ln in text.splitlines()
            if "\t" in ln and ln.split("\t", 1)[0].strip()]


def evaluate_quota(envelope: dict, model: str, min_quota: float):
    """None when there is headroom, else a refusal message."""
    groups = (((envelope or {}).get("command") or {}).get("data") or {}).get("groups")
    if not isinstance(groups, list):
        return "nao consegui ler os grupos de quota de `agy -p /usage --output-format json`"
    family = model.split("-", 1)[0].lower()
    hits = [g for g in groups if family in (str(g.get("name", "")) + " "
                                            + str(g.get("description", ""))).lower()]
    if not hits:
        return f"nenhum grupo de quota menciona {family!r}; formato do /usage mudou?"
    for g in hits:
        for b in g.get("buckets") or []:
            if b.get("disabled"):
                continue
            rf = b.get("remaining_fraction")
            if not isinstance(rf, (int, float)):
                return f"quota {g.get('name')}/{b.get('name')}: remaining_fraction ausente"
            if rf < min_quota:
                return (f"quota esgotada: {g.get('name')} / {b.get('name')} = {rf:.0%} "
                        f"(minimo {min_quota:.0%}); renova em {b.get('reset_time', '?')}")
    return None


def evaluate_run(rc, stdout: str, stderr: str, mode: str, schema: dict):
    """(failures, warnings, envelope). Exit 0 is never taken as success."""
    fails, warns = [], []
    strict_denials = mode == "delegate"
    if rc == "wrapper-timeout":
        fails.append("timeout do wrapper: agy nao terminou e foi encerrado")
    elif rc != 0:
        m = re.search(r"AGY_ERROR:\s*(\{.*\})", stderr)
        detail = m.group(1)[:400] if m else tail(stderr.strip(), 400)
        fails.append(f"agy saiu com rc={rc}: {detail}")
    if TIMEOUT_MARKER in stderr:
        fails.append("print timeout do agy: a saida e parcial (o agy sai com 0 mesmo assim)")
    if NO_OUTPUT_MARKER in stderr:
        fails.append("agy terminou sem saida e sem erro registrado")
    if AUTO_DENY_MARKER in stderr:
        (fails if strict_denials else warns).append(
            "permissao auto-negada em modo headless: " + tail(stderr.strip(), 300))
    env = None
    if not stdout.strip():
        fails.append("stdout vazio")
    else:
        try:
            env = json.loads(stdout)
        except ValueError:
            fails.append("stdout nao e o envelope JSON esperado: " + tail(stdout.strip(), 300))
    if isinstance(env, dict):
        if env.get("status") != "SUCCESS":
            fails.append(f"status={env.get('status')!r} error={str(env.get('error'))[:300]}")
        denied = env.get("denied_actions") or []
        if denied:
            (fails if strict_denials else warns).append(f"denied_actions: {json.dumps(denied)[:300]}")
        so = env.get("structured_output")
        if so is None:
            fails.append("structured_output nulo: o relatorio nao satisfez o schema "
                         "(o agy devolve status SUCCESS mesmo assim)")
        elif isinstance(so, dict):
            missing = [k for k in schema.get("required", []) if k not in so]
            if missing:
                fails.append(f"relatorio sem campos obrigatorios: {missing}")
            if mode == "delegate" and so.get("status") in ("partial", "blocked"):
                fails.append(f"o worker se declarou {so['status']!r}")
    return fails, warns, env


def snapshot_procs(repo: str) -> dict:
    """pid -> cmdline for processes whose cwd is inside the repo."""
    found = {}
    for pid in os.listdir("/proc"):
        if not pid.isdigit():
            continue
        try:
            cwd = os.readlink(f"/proc/{pid}/cwd")
            if cwd == repo or cwd.startswith(repo + "/"):
                with open(f"/proc/{pid}/cmdline", "rb") as fh:
                    found[int(pid)] = fh.read().replace(b"\0", b" ").decode(errors="replace").strip()[:200]
        except OSError:
            continue
    return found


def install_hooks(repo: str, rundir: str, ctx: dict) -> bool:
    """Write .agents/hooks.json. Returns whether .agents/ was created by us."""
    path = os.path.join(repo, HOOK_FILE)
    if os.path.lexists(path):
        raise Refusal(f"{HOOK_FILE} ja existe neste repo; o agy le um so arquivo de hooks por "
                      "workspace e este script nao sobrescreve o seu. Mova-o ou rode noutro worktree.")
    agents = os.path.dirname(path)
    created = not os.path.isdir(agents)
    os.makedirs(agents, exist_ok=True)
    base = f"{shlex.quote(sys.executable)} {shlex.quote(os.path.abspath(__file__))} hook"
    st = shlex.quote(rundir)
    gate_secs = ctx.get("gate_timeout", DEFAULT_GATE_TIMEOUT) * max(
        1, len(ctx["gate"]["format"]) + len(ctx["gate"]["checks"])) + 60
    spec = {"agy-worker": {
        "SessionStart": [{"type": "command", "command": f"{base} start --state {st}", "timeout": 10}],
        "PreToolUse": [{"matcher": "*", "hooks": [
            {"type": "command", "command": f"{base} pre --state {st}", "timeout": gate_secs}]}],
        "Stop": [{"type": "command", "command": f"{base} stop --state {st}", "timeout": gate_secs}],
    }}
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(spec, fh, indent=2)
    write_json(os.path.join(rundir, "hooks.installed.json"), spec)
    return created


def remove_hooks(repo: str, created_dir: bool) -> None:
    path = os.path.join(repo, HOOK_FILE)
    try:
        os.remove(path)
    except FileNotFoundError:
        pass
    if created_dir:
        try:
            os.rmdir(os.path.dirname(path))     # only if empty: never rm -r
        except OSError:
            pass


def preflight_agy(model: str, min_quota: float, probe_quota: bool, rundir: str):
    if not shutil.which("agy"):
        raise Refusal("agy nao esta no PATH")
    proc = subprocess.run(["agy", "models"], capture_output=True, text=True, timeout=120)
    slugs = parse_models(proc.stdout)
    if proc.returncode != 0 or not slugs:
        raise Refusal(f"`agy models` falhou (rc={proc.returncode}): {tail(proc.stderr.strip(), 300)}")
    if model not in slugs:
        raise Refusal(f"modelo {model!r} nao existe nesta conta. Disponiveis: {', '.join(slugs)}")
    if not probe_quota:
        return
    proc = subprocess.run(["agy", "-p", "/usage", "--output-format", "json"],
                          capture_output=True, text=True, timeout=120)
    with open(os.path.join(rundir, "usage.json"), "w", encoding="utf-8") as fh:
        fh.write(proc.stdout)
    try:
        env = json.loads(proc.stdout)
    except ValueError:
        env = None
    msg = evaluate_quota(env, model, min_quota)
    if msg:
        raise Refusal(msg + " (use --no-quota-probe para pular esta checagem)")


def run_agy(cmd: list, repo: str, rundir: str, timeout_s: int):
    out_p, err_p = os.path.join(rundir, "agy.stdout"), os.path.join(rundir, "agy.stderr")
    with open(out_p, "w") as fo, open(err_p, "w") as fe:
        proc = subprocess.Popen(cmd, cwd=repo, stdout=fo, stderr=fe, stdin=subprocess.DEVNULL,
                                start_new_session=True)
        try:
            rc = proc.wait(timeout=timeout_s + 180)
        except (subprocess.TimeoutExpired, KeyboardInterrupt) as exc:
            # Our own child's process group: we started it, so we stop it.
            for sig in (signal.SIGTERM, signal.SIGKILL):
                try:
                    os.killpg(proc.pid, sig)
                    proc.wait(timeout=10)
                    break
                except (ProcessLookupError, subprocess.TimeoutExpired):
                    continue
            if isinstance(exc, KeyboardInterrupt):
                raise
            rc = "wrapper-timeout"
    with open(out_p, encoding="utf-8", errors="replace") as fh:
        stdout = fh.read()
    with open(err_p, encoding="utf-8", errors="replace") as fh:
        stderr = fh.read()
    return rc, stdout, stderr


def new_rundir(repo: str, kind: str) -> str:
    base = state_base(repo)
    rundir = os.path.join(base, "runs", f"{time.strftime('%Y%m%d-%H%M%S')}-{kind}-{os.getpid()}")
    os.makedirs(rundir, exist_ok=True)
    return rundir


def guard_events(rundir: str):
    events = []
    try:
        with open(os.path.join(rundir, "guard.jsonl"), encoding="utf-8") as fh:
            for line in fh:
                try:
                    events.append(json.loads(line))
                except ValueError:
                    continue
    except OSError:
        pass
    return events


def _sigterm(_signo, _frame):
    raise KeyboardInterrupt


# --------------------------------------------------------------------------
# subcommands
# --------------------------------------------------------------------------

def base_ctx(repo, task, mode):
    return {
        "mode": mode, "repo": repo, "scope": task["scope"], "side_effects": task["side_effects"],
        "allow_paths": task["allow_paths"], "gate": task["gate"],
        "gate_timeout": task["gate_timeout"], "max_gate_attempts": task["max_gate_attempts"],
        "gate_commands": task["gate"]["format"] + task["gate"]["checks"],
        "deny_patterns": DENY_COMMANDS + [(p, "regra do projeto") for p in task["deny_commands"]],
    }


def cmd_delegate(a) -> int:
    signal.signal(signal.SIGTERM, _sigterm)
    task = load_task(a.task)
    if a.model:
        task["model"] = a.model
    repo = repo_root(a.repo or os.getcwd())
    git(repo, "rev-parse", "--verify", "HEAD")
    dirty = changed_paths(repo)
    if dirty:
        raise Refusal("arvore suja; commite ou guarde antes (o diff do worker tem que ser so dele): "
                      + ", ".join(dirty[:10]))
    if os.path.lexists(os.path.join(repo, HOOK_FILE)):
        raise Refusal(f"{HOOK_FILE} ja existe; outra execucao em curso ou hooks seus neste workspace")
    rundir = new_rundir(repo, "delegate")
    eprint(f"agy-worker: run dir {rundir}")
    preflight_agy(task["model"], task["min_quota"], not a.no_quota_probe, rundir)
    ctx = base_ctx(repo, task, "delegate")
    write_json(os.path.join(rundir, "ctx.json"), ctx)
    write_json(os.path.join(rundir, "task.json"), task)
    schema_path = os.path.join(rundir, "report.schema.json")
    write_json(schema_path, task["report_schema"])
    prompt = compose_prompt(task, repo)
    with open(os.path.join(rundir, "prompt.md"), "w", encoding="utf-8") as fh:
        fh.write(prompt)
    head = git(repo, "rev-parse", "HEAD").strip()
    before = snapshot_procs(repo)
    cmd = ["agy", "-p", prompt, "--model", task["model"], "--output-format", "json",
           "--json-schema", schema_path, "--print-timeout", f"{task['timeout']}s",
           "--dangerously-skip-permissions"]
    created = install_hooks(repo, rundir, ctx)
    started = time.time()
    try:
        eprint(f"agy-worker: agy rodando ({task['model']}, timeout {task['timeout']}s)…")
        rc, stdout, stderr = run_agy(cmd, repo, rundir, task["timeout"])
    finally:
        remove_hooks(repo, created)
    wall = round(time.time() - started)
    fails, warns, env = evaluate_run(rc, stdout, stderr, "delegate", task["report_schema"])
    events = guard_events(rundir)
    if not any(e.get("event") == "session_start" for e in events):
        fails.append("os hooks do agy-worker nao carregaram (nenhum SessionStart registrado): "
                     "o run nao teve guard rails; trate o diff como nao confiavel")
    if git(repo, "rev-parse", "HEAD").strip() != head:
        fails.append("HEAD mudou durante o run (commit ou checkout passou pelo guard)")
    # The gate verdict that counts is the one for the tree as it is now.
    st = read_json(os.path.join(rundir, "gate-state.json"), {"attempts": 0})
    fp = fingerprint(repo, task["side_effects"])
    if st.get("fingerprint") == fp and st.get("passed") is True:
        passed, text, source = True, st["text"], "cached (estado identico ao ultimo gate verde do hook)"
    else:
        passed, text, _ = run_gate(repo, ctx)
        with open(os.path.join(rundir, "gate-final.log"), "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
        source = "final (rodado apos o agy)"
    if not passed:
        fails.append("gate falhou no estado final da arvore")
    cls = classify(changed_paths(repo), task["scope"], task["side_effects"])
    if cls["out_of_scope"]:
        fails.append(f"alteracoes fora do escopo: {cls['out_of_scope']}")
    if cls["side_effects"]:
        warns.append(f"efeitos colaterais tolerados (revise e reverta se for o caso): {cls['side_effects']}")
    denials = [e for e in events if e.get("event") == "pre" and e.get("decision") != "allow"]
    if denials:
        warns.append(f"{len(denials)} chamada(s) negada(s) pelos guards; veja guard_denials")
    leftover = {p: c for p, c in snapshot_procs(repo).items() if p not in before and p != os.getpid()}
    if leftover:
        warns.append("processos novos com cwd no repo ainda vivos (nao foram encerrados): "
                     + "; ".join(f"{p} {c}" for p, c in leftover.items()))
    verdict = {
        "ok": not fails, "mode": "delegate", "run_dir": rundir, "model": task["model"],
        "failures": fails, "warnings": warns, "changed": cls,
        "gate": {"passed": passed, "source": source, "hook_attempts": st.get("attempts", 0),
                 "tail": tail(text, 2500)},
        "guard_denials": [{k: e.get(k) for k in ("tool", "reason", "args")} for e in denials[-20:]],
        "stop_events": [e for e in events if e.get("event") == "stop"],
        "report": (env or {}).get("structured_output") if isinstance(env, dict) else None,
        "agy": {"rc": rc, "wall_seconds": wall, **({k: env.get(k) for k in (
            "status", "duration_seconds", "num_turns", "usage", "conversation_id")}
            if isinstance(env, dict) else {})},
        "next": "Nada foi commitado. Revise `git diff HEAD` contra a fonte da verdade antes de aceitar; "
                "o gate e necessario, nao suficiente.",
    }
    write_json(os.path.join(rundir, "verdict.json"), verdict)
    print(json.dumps(verdict, ensure_ascii=False, indent=2))
    eprint(f"agy-worker: {'OK' if verdict['ok'] else 'FALHOU'} — {len(fails)} falha(s), "
           f"{len(warns)} aviso(s); verdict em {rundir}/verdict.json")
    return 0 if verdict["ok"] else 1


def cmd_review(a) -> int:
    signal.signal(signal.SIGTERM, _sigterm)
    repo = repo_root(a.repo or os.getcwd())
    question = " ".join(a.prompt).strip()
    if a.prompt_file:
        with open(a.prompt_file, encoding="utf-8") as fh:
            question = (fh.read() + "\n" + question).strip()
    if not question:
        raise Refusal("review sem pergunta: passe o texto ou --prompt-file")
    schema = DEFAULT_REVIEW_SCHEMA
    if a.schema:
        schema = read_json(a.schema)
        if not (isinstance(schema, dict) and schema.get("type") == "object"):
            raise Refusal(f"{a.schema}: schema precisa de raiz type=object")
    model = a.model or DEFAULT_MODEL
    timeout_s = parse_duration(a.timeout)
    diff_txt = ""
    if a.diff:
        diff_txt = git(repo, "diff", a.diff)
        if not diff_txt.strip():
            raise Refusal(f"git diff {a.diff} vazio")
        if len(diff_txt.encode()) > MAX_DIFF_BYTES:
            diff_txt = diff_txt.encode()[:MAX_DIFF_BYTES].decode(errors="ignore") + \
                "\n…(diff cortado; leia os arquivos para o resto)…"
    rundir = new_rundir(repo, "review")
    eprint(f"agy-worker: run dir {rundir}")
    preflight_agy(model, a.min_quota, not a.no_quota_probe, rundir)
    prompt = question
    if diff_txt:
        prompt += f"\n\n## Diff under review (`git diff {a.diff}`)\n```diff\n{diff_txt}\n```"
    prompt += ("\n\n---\nYou are a read-only reviewer. Do not modify files and do not run commands; "
               f"read files under `{repo}` as needed. Every finding must quote the exact code or text "
               "that supports it in `evidence`. Prefer `unsure` over a guess.\n")
    with open(os.path.join(rundir, "prompt.md"), "w", encoding="utf-8") as fh:
        fh.write(prompt)
    ctx = {"mode": "review", "repo": repo, "scope": [], "side_effects": [], "allow_paths": [],
           "gate": {"format": [], "checks": [], "forbid": []}, "gate_timeout": 60,
           "max_gate_attempts": 0, "gate_commands": [], "deny_patterns": DENY_COMMANDS}
    write_json(os.path.join(rundir, "ctx.json"), ctx)
    schema_path = os.path.join(rundir, "review.schema.json")
    write_json(schema_path, schema)
    fp_before = fingerprint(repo, [])
    cmd = ["agy", "-p", prompt, "--model", model, "--mode", "plan", "--output-format", "json",
           "--json-schema", schema_path, "--print-timeout", f"{timeout_s}s"]
    created = install_hooks(repo, rundir, ctx)
    try:
        eprint(f"agy-worker: review rodando ({model}, --mode plan)…")
        rc, stdout, stderr = run_agy(cmd, repo, rundir, timeout_s)
    finally:
        remove_hooks(repo, created)
    fails, warns, env = evaluate_run(rc, stdout, stderr, "review", schema)
    if fingerprint(repo, []) != fp_before:
        fails.append("a arvore mudou durante um review que devia ser somente leitura")
    if not any(e.get("event") == "session_start" for e in guard_events(rundir)):
        warns.append("hooks nao carregaram (nenhum SessionStart): o review rodou so com --mode plan")
    verdict = {"ok": not fails, "mode": "review", "run_dir": rundir, "model": model,
               "failures": fails, "warnings": warns,
               "report": env.get("structured_output") if isinstance(env, dict) else None,
               "agy": {"rc": rc, **({k: env.get(k) for k in ("status", "duration_seconds", "num_turns",
                                                             "usage")} if isinstance(env, dict) else {})},
               "next": "Segunda opiniao de um modelo mais barato: confira cada evidence no codigo antes de agir."}
    write_json(os.path.join(rundir, "verdict.json"), verdict)
    print(json.dumps(verdict, ensure_ascii=False, indent=2))
    return 0 if verdict["ok"] else 1


def cmd_gate(a) -> int:
    task = load_task(a.task)
    repo = repo_root(a.repo or os.getcwd())
    ctx = base_ctx(repo, task, "delegate")
    passed, text, _ = run_gate(repo, ctx, baseline=a.baseline)
    print(text)
    return 0 if passed else 1


# --------------------------------------------------------------------------
# self-test
# --------------------------------------------------------------------------

def self_test() -> int:
    n = 0

    def check(cond, msg):
        nonlocal n
        n += 1
        if not cond:
            raise AssertionError(msg)

    tmp = tempfile.mkdtemp(prefix="agy-worker-selftest-")
    try:
        repo = os.path.realpath(os.path.join(tmp, "repo"))
        os.makedirs(os.path.join(repo, "src"))
        g = ["git", "-C", repo, "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]
        subprocess.run(["git", "init", "-q", repo], check=True)
        with open(os.path.join(repo, "src", "a.txt"), "w") as fh:
            fh.write("one\n")
        with open(os.path.join(repo, "side.json"), "w") as fh:
            fh.write("{}\n")
        subprocess.run(g + ["add", "-A"], check=True)
        subprocess.run(g + ["commit", "-q", "-m", "init"], check=True)

        # example task shipped with the skill must validate
        example = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "skills",
                               "agy-worker", "task.example.json")
        t = load_task(example)
        check(t["scope"] and t["gate"]["checks"], "task.example.json carrega")
        check("Operating rules" in compose_prompt(t, repo), "prompt composto tem as regras")

        task = normalize_task({"prompt": "x", "scope": ["src/*"], "side_effects": ["side.json"],
                               "gate": {"format": ["ls -- {files} >/dev/null"], "checks": ["true"],
                                        "forbid": [r"@ts-ignore"]}})
        for bad, why in ((dict(prompt="", scope=["a"], gate={"checks": ["true"]}), "prompt vazio"),
                         (dict(prompt="x", scope=[], gate={"checks": ["true"]}), "scope vazio"),
                         (dict(prompt="x", scope=["../a"], gate={"checks": ["true"]}), "scope com .."),
                         (dict(prompt="x", scope=["a"], gate={}), "gate sem comandos"),
                         (dict(prompt="x", scope=["a"], gate={"checks": ["t"]},
                               report_schema={"type": "string"}), "schema sem raiz object")):
            try:
                normalize_task(bad)
                check(False, f"task invalida aceita: {why}")
            except Refusal:
                check(True, why)

        ctx = base_ctx(repo, task, "delegate")
        pre = lambda name, **args: decide_pre({"toolCall": {"name": name, "args": args}}, ctx)  # noqa: E731
        check(pre("view_file", AbsolutePath=f"{repo}/src/a.txt")["decision"] == "allow", "leitura no repo")
        check(pre("view_file", AbsolutePath="/etc/passwd")["decision"] == "deny", "leitura fora do repo")
        check(pre("list_dir", DirectoryPath="~/.claude")["decision"] == "deny", "home negado")
        check(pre("run_command", CommandLine="cat /tmp/x")["decision"] == "deny", "/tmp negado")
        check(pre("run_command", CommandLine="ls ..")["decision"] == "deny", ".. negado")
        check(pre("run_command", CommandLine="ps aux")["decision"] == "deny", "ps negado")
        check(pre("run_command", CommandLine="git commit -m x")["decision"] == "deny", "commit negado")
        check(pre("run_command", CommandLine="npm install left-pad")["decision"] == "deny", "install negado")
        check(pre("run_command", CommandLine="sed -i s/a/b/ src/a.txt")["decision"] == "deny", "sed -i negado")
        check(pre("run_command", CommandLine="echo $HOME")["decision"] == "deny", "$HOME negado")
        check(pre("run_command", CommandLine="npm test 2>&1 > /dev/null")["decision"] == "allow", "npm test")
        check(pre("run_command", CommandLine="git diff HEAD")["decision"] == "allow", "git diff permitido")
        check(pre("run_command", CommandLine="echo $((4 / 2))")["decision"] == "allow", "divisao nao e path")
        check(pre("run_command", CommandLine="sed -n 1,5p src/a.txt")["decision"] == "allow", "sed -n")
        check(pre("write_to_file", TargetFile=f"{repo}/src/b.txt", CodeContent="/etc/x")["decision"]
              == "allow", "escrita no escopo; conteudo nao e escaneado")
        check(pre("write_to_file", TargetFile=f"{repo}/side.json")["decision"] == "deny", "fora do escopo")
        check(pre("replace_file_content", TargetFile="src/../.git/config")["decision"] == "deny", ".git")
        check(pre("write_to_file", TargetFile="/tmp/out.txt")["decision"] == "deny", "escrita fora do repo")
        check(pre("invoke_subagent", Task="x")["decision"] == "deny", "subagente negado")
        check(pre("finish", files_changed=["/etc/passwd"])["decision"] == "allow", "finish nao e escaneado")
        check(pre("grep_search", SearchPath=repo, Query="/api/v1")["decision"] == "allow", "Query ignorada")
        check(pre("read_url_content", Url="https://example.com/a/b")["decision"] == "allow", "URL nao e path")
        dctx = dict(ctx, gate_commands=["docker compose run test", "{files}"])
        dpre = lambda c: decide_pre({"toolCall": {"name": "run_command", "args": {"CommandLine": c}}}, dctx)  # noqa: E731
        check(dpre("docker compose run test")["decision"] == "allow", "comando do gate isento")
        check(dpre("docker compose run test && git push")["decision"] == "deny", "encadeado nao e isento")
        check(dpre("docker ps")["decision"] == "deny", "prefixo vazio nao isenta tudo")

        # gate: nothing changed -> fail; in-scope change -> pass; forbid; out of scope
        ok, text, _ = run_gate(repo, ctx)
        check(not ok and "nenhum arquivo do escopo" in text, "gate falha sem mudanca")
        ok, text, _ = run_gate(repo, ctx, baseline=True)
        check(ok and "pulado" in text, "baseline roda so comandos")
        with open(os.path.join(repo, "src", "a.txt"), "a") as fh:
            fh.write("two\n")
        with open(os.path.join(repo, "src", "new file.txt"), "w") as fh:
            fh.write("ok\n")
        ok, text, cls = run_gate(repo, ctx)
        check(ok, f"gate passa com mudanca no escopo: {text}")
        check(sorted(cls["in_scope"]) == ["src/a.txt", "src/new file.txt"], "classifica escopo")
        with open(os.path.join(repo, "src", "a.txt"), "a") as fh:
            fh.write("x // @ts-ignore\n")
        ok, text, _ = run_gate(repo, ctx)
        check(not ok and "src/a.txt:3" in text, f"forbid com numero de linha: {text}")
        subprocess.run(g + ["checkout", "-q", "--", "src/a.txt"], check=True)
        with open(os.path.join(repo, "side.json"), "w") as fh:
            fh.write('{"analytics": false}\n')
        with open(os.path.join(repo, "other.txt"), "w") as fh:
            fh.write("x\n")
        ok, text, cls = run_gate(repo, ctx)
        check(not ok and "other.txt" in text and cls["side_effects"] == ["side.json"],
              "fora do escopo falha; efeito colateral tolerado")
        os.remove(os.path.join(repo, "other.txt"))
        ok, text, _ = run_gate(repo, dict(ctx, gate=dict(ctx["gate"], checks=['test "$AGY_WORKER_GATE" = 1'])))
        check(ok, "gate exporta AGY_WORKER_GATE")
        ctx2 = dict(ctx, gate=dict(ctx["gate"], checks=["false"]))
        ok, text, _ = run_gate(repo, ctx2)
        check(not ok and "FALHOU (rc=1)" in text, "check falhando reprova")

        # fingerprint ignores side effects and changes with in-scope edits
        fp1 = fingerprint(repo, ["side.json"])
        with open(os.path.join(repo, "side.json"), "w") as fh:
            fh.write('{"analytics": true}\n')
        check(fingerprint(repo, ["side.json"]) == fp1, "fingerprint ignora efeito colateral")
        with open(os.path.join(repo, "src", "new file.txt"), "a") as fh:
            fh.write("more\n")
        check(fingerprint(repo, ["side.json"]) != fp1, "fingerprint muda com o escopo")

        # hooks end to end through a subprocess: never `{}` for pre, gate cache
        rundir = os.path.join(tmp, "run")
        os.makedirs(rundir)
        write_json(os.path.join(rundir, "ctx.json"), dict(ctx, max_gate_attempts=4))

        def hook(event, payload):
            p = subprocess.run([sys.executable, os.path.abspath(__file__), "hook", event, "--state", rundir],
                               input=json.dumps(payload), capture_output=True, text=True, timeout=60)
            return json.loads(p.stdout)
        check(hook("start", {"modelName": "m"}) == {}, "start devolve {}")
        check(hook("pre", {"toolCall": {"name": "view_file", "args": {"AbsolutePath": "/etc/x"}}})
              ["decision"] == "deny", "hook pre nega")
        check(hook("pre", {"toolCall": {"name": "list_dir", "args": {"DirectoryPath": repo}}})
              == {"decision": "allow"}, "hook pre permite explicitamente")
        r = hook("stop", {"terminationReason": "NO_TOOL_CALL"})
        check(r["decision"] == "stop", f"stop com gate verde para: {r}")
        r = hook("pre", {"toolCall": {"name": "finish", "args": {}}})
        check(r["decision"] == "allow", "finish com gate verde")
        st = read_json(os.path.join(rundir, "gate-state.json"))
        check(st["attempts"] == 2 and st["runs"] == 1, f"cache do gate: {st}")
        with open(os.path.join(repo, "outside.txt"), "w") as fh:
            fh.write("x\n")
        r = hook("stop", {"terminationReason": "TERMINAL_STEP_TYPE"})
        check(r["decision"] == "continue" and "outside.txt" in r["reason"], "stop com gate vermelho continua")
        r = hook("stop", {"terminationReason": "MAX_INVOCATIONS"})
        check(r["decision"] == "stop", "outros motivos param sem gate")
        r = hook("pre", {"toolCall": {"name": "finish", "args": {}}})
        check(r["decision"] == "allow", "limite de tentativas libera o finish")
        st = read_json(os.path.join(rundir, "gate-state.json"))
        check(st["runs"] == 3, f"falha nunca vem do cache: {st}")
        os.remove(os.path.join(rundir, "ctx.json"))
        check(hook("pre", {"toolCall": {"name": "view_file", "args": {}}})["decision"] == "deny",
              "guard quebrado nega em vez de devolver {}")
        check(hook("stop", {})["decision"] == "stop", "stop quebrado deixa parar")
        events = guard_events(rundir)
        check(any(e.get("event") == "session_start" for e in events), "marcador de SessionStart")

        # result evaluation: the exit-0 failure modes
        sch = DEFAULT_REPORT_SCHEMA
        good = {"status": "SUCCESS", "structured_output": {"status": "done", "files_changed": [],
                "checks_run": [], "divergences": [], "out_of_scope_needs": []}}
        f, w, _ = evaluate_run(0, json.dumps(good), "", "delegate", sch)
        check(f == [] and w == [], f"run bom: {f}")
        f, _, _ = evaluate_run(0, "", "", "delegate", sch)
        check(any("stdout vazio" in x for x in f), "stdout vazio")
        f, _, _ = evaluate_run(0, json.dumps(dict(good, structured_output=None)), "", "delegate", sch)
        check(any("structured_output nulo" in x for x in f), "schema nao satisfeito")
        f, _, _ = evaluate_run(0, json.dumps(good), "[agy] print timeout after 5s with turn", "delegate", sch)
        check(any("timeout" in x for x in f), "marcador de timeout")
        den = dict(good, denied_actions=[{"action": "command"}])
        f, _, _ = evaluate_run(0, json.dumps(den), "", "delegate", sch)
        check(any("denied_actions" in x for x in f), "denied_actions reprova delegate")
        f, w, _ = evaluate_run(0, json.dumps(dict(den, structured_output={"verdict": "approve",
                               "findings": [], "summary": ""})), "", "review", DEFAULT_REVIEW_SCHEMA)
        check(f == [] and w, "denied_actions so avisa no review")
        f, _, _ = evaluate_run(1, "", "error: invalid model selection", "delegate", sch)
        check(any("rc=1" in x for x in f), "rc != 0")
        part = dict(good, structured_output=dict(good["structured_output"], status="partial"))
        f, _, _ = evaluate_run(0, json.dumps(part), "", "delegate", sch)
        check(any("partial" in x for x in f), "worker parcial reprova")
        f, _, _ = evaluate_run(0, json.dumps(dict(good, structured_output={"status": "done"})), "",
                               "delegate", sch)
        check(any("obrigatorios" in x for x in f), "campos obrigatorios")

        # quota and models, against the shapes agy 1.3.4 printed on 2026-10-13
        usage = {"command": {"data": {"groups": [
            {"name": "Gemini Models", "description": "Models within this group: Gemini Flash, Gemini Pro",
             "buckets": [{"name": "Weekly", "remaining_fraction": 0.73},
                         {"name": "Five Hour", "remaining_fraction": 0.45}]},
            {"name": "Claude and GPT models", "description": "Claude Opus, Claude Sonnet, GPT-OSS",
             "buckets": [{"name": "Weekly", "remaining_fraction": 0, "reset_time": "2026-10-15T18:34:47Z"},
                         {"name": "Five Hour", "disabled": True, "remaining_fraction": 1}]}]}}}
        check(evaluate_quota(usage, "gemini-3.8-flash-low", 0.05) is None, "quota gemini ok")
        msg = evaluate_quota(usage, "claude-opus-5-5-high", 0.05)
        check(msg and "esgotada" in msg and "2026-10-15" in msg, "quota claude esgotada")
        check(evaluate_quota(usage, "gpt-oss-120b-medium", 0.05), "gpt no mesmo grupo esgotado")
        check(evaluate_quota({}, "gemini-x", 0.05), "usage ilegivel recusa")
        models = parse_models("gemini-3.8-flash-low\tGemini 3.8 Flash (Low)\nFetching available models...\n")
        check(models == ["gemini-3.8-flash-low"], "parse de agy models")

        # install/remove hooks leaves nothing behind and refuses to clobber
        subprocess.run(g + ["checkout", "-q", "--", "."], check=True)
        subprocess.run(g + ["clean", "-q", "-fd"], check=True)
        created = install_hooks(repo, rundir, ctx)
        spec = read_json(os.path.join(repo, HOOK_FILE))
        check(set(spec["agy-worker"]) == {"SessionStart", "PreToolUse", "Stop"}, "hooks.json gerado")
        check(changed_paths(repo) == [], "hooks.json nao conta como mudanca")
        try:
            install_hooks(repo, rundir, ctx)
            check(False, "sobrescreveu hooks.json existente")
        except Refusal:
            check(True, "recusa sobrescrever")
        remove_hooks(repo, created)
        check(not os.path.exists(os.path.join(repo, ".agents")), ".agents removido")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"self-test: {n} checks ok")
    return 0


# --------------------------------------------------------------------------

def main(argv=None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    if argv == ["--self-test"]:
        return self_test()
    p = argparse.ArgumentParser(prog="agy_worker.py", description=__doc__.split("\n\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("delegate", help="roda uma task sob guard rails e gate")
    d.add_argument("task")
    d.add_argument("--model")
    d.add_argument("--repo")
    d.add_argument("--no-quota-probe", action="store_true")
    r = sub.add_parser("review", help="segunda opiniao somente leitura (--mode plan)")
    r.add_argument("prompt", nargs="*")
    r.add_argument("--prompt-file")
    r.add_argument("--diff", help="intervalo para `git diff`, ex.: HEAD~1 ou main...HEAD")
    r.add_argument("--schema")
    r.add_argument("--model")
    r.add_argument("--repo")
    r.add_argument("--timeout", default=DEFAULT_REVIEW_TIMEOUT)
    r.add_argument("--min-quota", type=float, default=DEFAULT_MIN_QUOTA)
    r.add_argument("--no-quota-probe", action="store_true")
    gt = sub.add_parser("gate", help="roda o gate de uma task na arvore atual")
    gt.add_argument("task")
    gt.add_argument("--repo")
    gt.add_argument("--baseline", action="store_true",
                    help="so os comandos de format/checks, sem escopo nem forbid")
    h = sub.add_parser("hook", help="handler de hook do agy (instalado por run)")
    h.add_argument("event", choices=["pre", "stop", "start"])
    h.add_argument("--state", required=True)
    a = p.parse_args(argv)
    if a.cmd == "hook":
        return hook_main(a.event, a.state)
    try:
        return {"delegate": cmd_delegate, "review": cmd_review, "gate": cmd_gate}[a.cmd](a)
    except Refusal as exc:
        eprint(f"agy-worker: recusado: {exc}")
        print(json.dumps({"ok": False, "refused": True, "failures": [str(exc)]}, ensure_ascii=False))
        return 2
    except KeyboardInterrupt:
        eprint("agy-worker: interrompido; hooks removidos")
        return 130


if __name__ == "__main__":
    sys.exit(main())
