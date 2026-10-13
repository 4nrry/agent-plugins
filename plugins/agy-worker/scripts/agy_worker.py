#!/usr/bin/env python3
"""agy-worker: run Google's Antigravity CLI (`agy`) headless as a guarded worker.

Claude plans and reviews; agy executes one well-scoped slice. This script is
the guard rail between them. Subcommands:

  delegate TASK.json   run the task under agy with guard hooks and a gate
  review [PROMPT...]   read-only second opinion (agy: --mode plan + --json-schema)
  gate TASK.json       run the task's gate by hand (--baseline: commands only)
  hook pre|stop|start  agy workspace hook handlers (installed per run)
  hook oc-pre          the opencode guard plugin's handler (same policy)
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

Second backend, `"backend": "opencode"` in the task (opencode 1.19.0): the
guard is an opencode plugin generated in the run dir and loaded only through
that run's OPENCODE_CONFIG_CONTENT; it forwards every tool call to `hook
oc-pre`, which translates it and asks the same decide_pre. opencode has no
stop hook and no --json-schema, so the gate loop (run, gate, `run -s` with the
gate output) and the report parsing are here, and opencode.json's bytes are
restored after every opencode process (it writes "$schema" into it).
"""

import argparse
import fnmatch
import hashlib
import json
import os
import pathlib
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
TESTED_AGY_VERSION = "1.3.4"       # every agy behaviour this script relies on was seen on this one
MAX_PROMPT_BYTES = 100_000          # one argv string is capped at 128 KiB on Linux
MAX_DIFF_BYTES = 60_000
TAIL_CHARS = 6000
BACKENDS = ("agy", "opencode")
OPENCODE_DEFAULT_MODEL = "opencode/longcat-2.5-preview-free"
TESTED_OPENCODE_VERSION = "1.19.0"
# opencode writes "$schema" into these, in the process cwd, on every run (seen
# on 1.19.0 even with --dir); the driver restores their bytes after each run.
OPENCODE_CONFIG_FILES = ("opencode.json", "opencode.jsonc")
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

# An allowlist, not a denylist: any other tool (network, subagents, schedules,
# run_workflow's own python3 process, MCP tools, whatever a new agy adds) has
# effects these hooks cannot see. These are the file and shell tools; the
# smoke runs used only view_file, write_to_file, replace_file_content,
# run_command and finish.
ALLOWED_TOOLS = {"view_file", "list_dir", "find_by_name", "grep_search", "write_to_file",
                 "replace_file_content", "multi_replace_file_content", "run_command"}

SYSTEM_PATHS = ("/dev/null", "/dev/stdout", "/dev/stderr", "/usr/bin",
                "/bin", "/usr/local/bin")

# git global options that may sit between `git` and the subcommand.
_GIT_OPTS = r"(?:(?:-[cC]\s+\S+|--[\w-]+(?:=\S+)?|-[abd-zABD-Z])\s+)*"
# Start of a simple command: the line start or after an operator.
_CMD = r"(?:^|[;&|(\n`]|\$\()\s*"

DENY_COMMANDS = [
    (r"\bgit\s+" + _GIT_OPTS + r"(?!(?:status|diff|log|show|ls-files|ls-tree|grep|blame|"
     r"shortlog|describe|cat-file|rev-list|merge-base|add|rm|mv)\b)[^\s-]",
     "git fora da lista de leitura (status, diff, log, show, grep, add...)"),
    (r"\bgit\b.*--(git-dir|git-path|git-common-dir|absolute-git-dir)\b", "caminho do .git"),
    (r"(^|[\s/='\"<>:])\.(git|agents)($|[\s/'\"])", "acesso ao .git ou ao .agents"),
    (r"\brm\s(?:[^;&|\n]*\s)?(?:-[a-zA-Z]*[rR][a-zA-Z]*|--recursive)(\s|$)", "rm recursivo"),
    (r"\bfind\b[^;&|\n]*\s-(delete|exec|execdir|ok|okdir|fprint\w*|fls)\b", "find que escreve ou executa"),
    (_CMD + r"(ln|chmod|chown|chgrp|crontab|at|batch|nohup|setsid|disown|systemctl|service)(\s|$)",
     "link, permissao, agendamento ou processo destacado"),
    (r"(^|[^&>|])&($|[^&>])", "processo em segundo plano (&)"),
    (r"\b(npm|pnpm|yarn|bun)\s+(install|i|ci|add|remove|rm|uninstall|update|"
     r"upgrade|up|link|publish)\b", "install ou publish de pacote"),
    (r"\b(pip3?|poetry|cargo|gem|composer)\s+(install|add|remove|uninstall|publish)\b"
     r"|\bgo\s+(get|install)\b|\buv\s+(add|remove|sync|pip\s+install)\b",
     "install de pacote"),
    (r"\b(apt|apt-get|dnf|yum|pacman|brew|snap|flatpak)\b", "gerenciador de pacotes do sistema"),
    (r"\b(npx|bunx)\s+(-y|--yes)\b|\bpnpm\s+dlx\b", "execucao de pacote baixado"),
    (r"(^|[\s;|&(])(sudo|su|doas)(\s|$)", "elevacao de privilegio"),
    (r"\b(npm|pnpm|yarn|bun|npx|nx|make|just|task|turbo)\b[^;&|\n]*\b(deploy|publish|release)\b",
     "deploy ou publish"),
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
    (r"(^|[\s=:'\"(/<>;&|])\.\.($|[\s/;&|)'\"])", "caminho com .."),
    (r"\$\{?HOME\b|\bprintenv\b|(^|[\s;|&])env\s*($|[;|&])", "home ou ambiente do usuario"),
]

# opencode only: its models write through bash where agy's use the edit tools
# (lab: `printf x > top.txt` past an edit-deny glob), so the file-writing
# coreutils are denied too. Added to the same deny list, never a second policy.
OPENCODE_DENY_COMMANDS = [
    (_CMD + r"(cp|mv|touch|mkdir|rmdir|rm|truncate|install|patch)(\s|$)",
     "escrita de arquivo pelo shell (use write/edit)"),
]
REVIEW_DENY_ALL = [(r"[\s\S]", "review somente leitura: sem shell")]

# opencode tool -> (the agy tool decide_pre knows, {opencode arg: agy arg}).
# The guard plugin forwards every call here, so one policy covers both.
OC_TOOLS = {
    "read": ("view_file", {"filePath": "AbsolutePath"}),
    "list": ("list_dir", {"path": "DirectoryPath"}),
    "glob": ("find_by_name", {"path": "SearchDirectory", "pattern": "Pattern"}),
    "grep": ("grep_search", {"path": "SearchPath", "pattern": "Query", "include": "Includes"}),
    "write": ("write_to_file", {"filePath": "TargetFile", "content": "CodeContent"}),
    "edit": ("replace_file_content", {"filePath": "TargetFile", "oldString": "TargetContent",
                                      "newString": "ReplacementContent"}),
    "multiedit": ("multi_replace_file_content", {"filePath": "TargetFile", "edits": "ReplacementChunks"}),
    "bash": ("run_command", {"command": "CommandLine", "workdir": "Cwd"}),
}
OC_INERT_TOOLS = {"todowrite", "todoread", "skill", "invalid"}   # no file or process effect
PATCH_TARGET = re.compile(r"^\*\*\* (?:(?:Add|Update|Delete) File|Move to):\s*(.+?)\s*$", re.M)

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
    # The worker could have planted config in the repo; our own git calls must
    # not run it (fsmonitor and hooks execute programs, ext diff too).
    proc = subprocess.run(["git", "-C", repo, "-c", "color.ui=false", "-c", "core.fsmonitor=false",
                           "-c", "core.hooksPath=/dev/null", *args],
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

def load_task(path: str, **overrides) -> dict:
    path = os.path.abspath(path)
    task = read_json(path)
    if not isinstance(task, dict):
        raise Refusal(f"{path}: nao e um objeto JSON legivel")
    task.update({k: v for k, v in overrides.items() if v})
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
    backend = task.get("backend", "agy")
    if backend not in BACKENDS:
        errs.append(f"backend {backend!r}: use um de {BACKENDS}")
    elif backend == "opencode" and isinstance(scope, list) and any(
            in_globs(f, scope) for f in OPENCODE_CONFIG_FILES):
        errs.append("scope cobre opencode.json(c), que o driver restaura depois de cada run do opencode")
    if not isinstance(task.get("disable_claude_code", False), bool):
        errs.append("disable_claude_code deve ser booleano")
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
        "backend": backend,
        "disable_claude_code": task.get("disable_claude_code", False),
        "model": task.get("model", OPENCODE_DEFAULT_MODEL if backend == "opencode" else DEFAULT_MODEL),
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
{report_rule(task)}"""


def report_rule(task: dict) -> str:
    """opencode has no --json-schema: the report is the last JSON object in
    the final message, and the driver asks again if it is missing."""
    if task.get("backend") != "opencode":
        return ""
    return ("- End your final message with the report as ONE JSON object (no prose after it) matching "
            f"this JSON schema: {json.dumps(task['report_schema'], separators=(',', ':'))}\n")


# --------------------------------------------------------------------------
# PreToolUse guard (pure)
# --------------------------------------------------------------------------

PATH_TOKEN = re.compile(r"""(?:^|[\s=:"'(,\[<>|;&])(~[A-Za-z0-9._/+@-]*|/[A-Za-z0-9._~/+@*?\[\]-]*)""")
GLOB_CHARS = set("*?[")


def arg_strings(v, key=""):
    """(key, string) for every non-content string in a tool's args."""
    if isinstance(v, str):
        yield key, v
    elif isinstance(v, dict):
        for k, x in v.items():
            if k not in CONTENT_KEYS:
                yield from arg_strings(x, k)
    elif isinstance(v, list):
        for x in v:
            yield from arg_strings(x, key)


def shell_path_tokens(cmd: str):
    """Absolute and ~ paths written literally in a shell command."""
    for m in PATH_TOKEN.finditer(cmd):
        tok = m.group(1)
        if tok.startswith("~"):
            if tok == "~" or tok.startswith("~/"):
                yield tok
            continue
        tok = "/" + tok.lstrip("/")             # `//etc` is `/etc`
        if tok == "/":
            continue                            # `$((4 / 2))`; `cd /` is caught by the cd check
        first = tok.split("/")[1]
        # A path whose top-level directory does not exist cannot be read, and a
        # non-root worker cannot create one: `grep '/api/v1'`, `sed -n '/a/,/b/p'`.
        if not (GLOB_CHARS & set(first)) and not os.path.lexists("/" + first):
            continue
        yield tok


def path_allowed(tok: str, repo: str, extra) -> bool:
    p = os.path.realpath(os.path.expanduser(tok))
    for base in (repo, *SYSTEM_PATHS, *extra):
        base = os.path.realpath(os.path.expanduser(base))
        if p == base or p.startswith(base.rstrip("/") + "/"):
            return True
    return False


def resolve(path: str, base: str) -> str:
    """Real path of `path`, relative ones taken from `base`; symlinks followed."""
    return os.path.realpath(os.path.join(base, os.path.expanduser(path)))


def unquote_shell(cmd: str) -> str:
    """The command with quote and escape characters dropped, contents kept, so
    `g''it push` and `"git" push` read as `git push` for the deny list."""
    return re.sub(r"['\"\\]", "", cmd)


def strip_quoted(cmd: str) -> str:
    """The command with quoted strings emptied: `grep '->' x` has no redirect."""
    return re.sub(r"'[^']*'|\"(?:[^\"\\]|\\.)*\"", "''", cmd)


def writes_by_redirect(cmd: str) -> bool:
    """True when the shell itself writes a file (`> f`, `>> f`, `&> f`, `tee`
    is in the deny list); redirects to /dev/null and between fds are fine."""
    s = strip_quoted(cmd)
    s = re.sub(r"\d*>&\d+|&>>?\s*/dev/null|\d*>>?\s*/dev/(null|stdout|stderr)\b", " ", s)
    return ">" in s


CD_TARGET = re.compile(r"(?:^|[;&|(\n])\s*(?:cd|pushd)\b\s*([^\s;&|)]*)")


def is_gate_command(cmd: str, gate_cmds) -> bool:
    """The worker is told to run the gate itself, so a gate command is never
    blocked by the generic deny list -- but only the command itself, plus
    redirects to /dev/null or between fds. Anything else after it (chaining,
    a newline, a substitution, a variable, a file redirect) goes through the
    full check."""
    cmd = cmd.strip()
    for gc in gate_cmds:
        prefix = gc.split("{files}")[0].strip()
        if not prefix or not cmd.startswith(prefix):
            continue
        rest = cmd[len(prefix):]
        if rest and not rest[0].isspace() and not prefix[-1].isspace():
            continue                            # `true` must not exempt `trueX`
        rest = re.sub(r"\s\d*>&\d+|\s\d*>>?\s*/dev/null\b", " ", rest)
        if not re.search(r"[;&|`$<>(){}\n\r\\]", rest):
            return True
    return False


def deny(reason: str) -> dict:
    return {"decision": "deny", "reason": reason}


def decide_pre(payload: dict, ctx: dict) -> dict:
    """Decision for every tool call except the gate on `finish`. Always explicit."""
    call = payload.get("toolCall") or {}
    name = call.get("name", "")
    args = call.get("args") or {}
    if not isinstance(args, dict):
        args = {}
    repo = ctx["repo"]
    extra = ctx.get("allow_paths", [])
    if name in FINISH_TOOLS:
        return {"decision": "allow"}
    if name not in ALLOWED_TOOLS:
        return deny(f"Ferramenta {name} bloqueada neste worker: so as ferramentas de arquivo e o "
                    "run_command passam pelos guard rails. Faca o trabalho com elas, dentro do escopo.")
    outside = (f"Trabalhe so dentro de {repo}. O gate esta descrito no enunciado; nao procure por ele.")
    # Path-valued arguments (AbsolutePath, DirectoryPath, SearchPath, Cwd,
    # TargetFile...), relative ones included, resolved through symlinks.
    for key, val in arg_strings(args):
        if key == "CommandLine" or "://" in val:
            continue
        if val.startswith(("/", "~", ".")) or "/" in val:
            if not path_allowed(resolve(val, repo), repo, extra):
                return deny(f"Acesso fora do repositorio bloqueado: {key}={val}. {outside}")
    target = args.get("TargetFile")
    if isinstance(target, str) and target:
        rel = os.path.relpath(resolve(target, repo), repo)
        if rel.startswith("..") or rel.split("/")[0] in (".git", ".agents"):
            return deny(f"Escrita fora da area de trabalho: {target}.")
        if not in_globs(rel, ctx.get("scope", [])):
            allowed = " ".join(ctx.get("scope", [])) or "(nenhum: modo somente leitura)"
            return deny(f"Fora do escopo desta tarefa: {rel}. Permitidos: {allowed}. Nao contorne pelo "
                        "shell; se outro arquivo precisar mudar, diga no relatorio (out_of_scope_needs).")
    cmd = args.get("CommandLine")
    if isinstance(cmd, str) and cmd.strip():
        for tok in shell_path_tokens(cmd):
            if not path_allowed(tok, repo, extra):
                return deny(f"Acesso fora do repositorio bloqueado: {tok}. {outside}")
        cwd = args.get("Cwd") if isinstance(args.get("Cwd"), str) and args.get("Cwd") else repo
        for m in CD_TARGET.finditer(cmd):
            dest = m.group(1)
            if dest in ("", "-") or not path_allowed(resolve(dest, cwd), repo, extra):
                return deny(f"cd para fora do repositorio bloqueado: {m.group(0).strip()!r}. {outside}")
        if is_gate_command(cmd, ctx.get("gate_commands", [])):
            return {"decision": "allow"}
        bare = unquote_shell(cmd)
        for pat, label in ctx.get("deny_patterns", []):
            if re.search(pat, cmd) or re.search(pat, bare):
                return deny(f"Comando bloqueado ({label}): {cmd!r}. Edite so com as ferramentas de edicao; "
                            "sem commit, push, install, deploy, migracao, rede ou processos. Testes, lint, "
                            "typecheck e leitura sao permitidos.")
        if writes_by_redirect(cmd):
            return deny(f"Escrita pelo shell bloqueada (redirecionamento para arquivo): {cmd!r}. Use as "
                        "ferramentas de edicao; redirecione saida so para /dev/null ou 2>&1.")
    return {"decision": "allow"}


def oc_calls(tool: str, args: dict) -> list:
    """An opencode tool call as the agy-shaped payloads decide_pre judges: one
    per file an apply_patch touches, none for tools without effects. Unknown
    tools keep their name, so the allowlist denies them."""
    if tool in OC_INERT_TOOLS:
        return []
    if tool == "apply_patch":
        targets = PATCH_TARGET.findall(str(args.get("patchText", "")))
        return ([{"toolCall": {"name": "write_to_file", "args": {"TargetFile": t}}} for t in targets]
                or [{"toolCall": {"name": "apply_patch", "args": {}}}])
    name, keys = OC_TOOLS.get(tool, (tool, {}))
    mapped = {keys.get(k, "Description" if k == "description" else k): v for k, v in args.items()}
    return [{"toolCall": {"name": name, "args": mapped}}]


def decide_oc(payload: dict, ctx: dict) -> dict:
    args = payload.get("args") if isinstance(payload.get("args"), dict) else {}
    for call in oc_calls(str(payload.get("tool", "")), args):
        out = decide_pre(call, ctx)
        if out["decision"] != "allow":
            return out
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
            h.update(git(repo, "diff", "--no-ext-diff", "HEAD", "--binary", "--", p, binary=True))
        else:
            try:
                with open(os.path.join(repo, p), "rb") as fh:
                    h.update(fh.read())
            except OSError:
                h.update(b"<missing>")
    return h.hexdigest()


def integrity_state(repo: str, rundir: str) -> dict:
    """Hashes of what a worker could use to run code or hide changes: git
    config, hooks and excludes, index flags that hide edits from `git status`,
    and this run's own ctx.json. Compared before and after the run."""
    state = {}
    dirs = {git(repo, "rev-parse", "--path-format=absolute", "--git-dir").strip(),
            git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir").strip()}
    files = [os.path.join(rundir, "ctx.json")]
    for d in dirs:
        files += [os.path.join(d, f) for f in ("config", "config.worktree", "info/exclude")]
        hooks = os.path.join(d, "hooks")
        if os.path.isdir(hooks):
            files += [os.path.join(hooks, f) for f in sorted(os.listdir(hooks))]
    for f in files:
        try:
            with open(f, "rb") as fh:
                state[f] = hashlib.sha256(fh.read()).hexdigest()
        except OSError:
            state[f] = None
    flagged = [r[2:] for r in git(repo, "ls-files", "-v", "-z").split("\0")
               if len(r) > 2 and (r[0].islower() or r[0] == "S")]
    state["<assume-unchanged/skip-worktree>"] = ",".join(sorted(flagged))
    return state


def ignored_state(repo: str) -> dict:
    """Ignored files (not directories, which `--directory` collapses) with
    size and mtime: `git status` never shows them, so a write to `.env` would
    otherwise go unseen. Directories are left out because caches and build
    output (`__pycache__/`, `dist/`) change on every gate run."""
    out = {}
    for p in git(repo, "ls-files", "-z", "-o", "-i", "--exclude-standard", "--directory").split("\0"):
        if not p or p.endswith("/"):
            continue
        try:
            st = os.lstat(os.path.join(repo, p))
            out[p] = (st.st_size, st.st_mtime_ns)
        except OSError:
            continue
    return out


def diff_state(before: dict, after: dict) -> list:
    return sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))


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
    for line in git(repo, "diff", "--no-ext-diff", "HEAD", "-U0", "--", path).splitlines():
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
            # AGY_WORKER_GATE lets a command tell the gate run from the
            # worker's own run of the same command. Own session, so a timeout
            # kills the whole tree the command started, not just bash.
            proc = subprocess.Popen(["bash", "-c", cmd], cwd=repo, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, text=True, start_new_session=True,
                                    env={**os.environ, "AGY_WORKER_GATE": "1"})
            try:
                out, _ = proc.communicate(timeout=ctx.get("gate_timeout", DEFAULT_GATE_TIMEOUT))
                rc = proc.returncode
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                out, _ = proc.communicate()
                rc = "timeout"
            out = out or ""
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
        elif event == "oc-pre":
            out = decide_oc(payload, ctx)
            entry = {"event": "pre", "tool": payload.get("tool"), "decision": out["decision"]}
            if out["decision"] != "allow":
                entry["reason"] = out.get("reason", "")[:300]
                entry["args"] = {k: (v if len(str(v)) < 300 else str(v)[:300] + "…")
                                 for k, v in (payload.get("args") or {}).items()
                                 if k not in ("content", "oldString", "newString", "patchText")}
            append_jsonl(log, entry)
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
               if event in ("pre", "oc-pre") else {"decision": "stop"} if event == "stop" else {})
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
    env, parsed = None, False
    if not stdout.strip():
        fails.append("stdout vazio")
    else:
        try:
            env, parsed = json.loads(stdout), True
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
    elif parsed:
        env = None
        fails.append(f"stdout e JSON mas nao um objeto: {tail(stdout.strip(), 200)}")
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


def refuse_existing_hooks(repo: str) -> None:
    path = os.path.join(repo, HOOK_FILE)
    if not os.path.lexists(path):
        return
    spec = read_json(path)
    if isinstance(spec, dict) and list(spec) == ["agy-worker"]:
        raise Refusal(f"{path} e sobra de um run do agy-worker que morreu sem limpar (SIGKILL?), ou "
                      "de um run ainda em curso neste workspace. Se nenhum `agy` estiver rodando aqui, "
                      f"remova so esse arquivo: rm {shlex.quote(path)}. Enquanto ele existir, um `agy` "
                      "interativo nesta pasta carrega os guards de um run morto.")
    raise Refusal(f"{HOOK_FILE} ja existe neste repo; o agy le um so arquivo de hooks por "
                  "workspace e este script nao sobrescreve o seu. Mova-o ou rode noutro worktree.")


def install_hooks(repo: str, rundir: str, ctx: dict) -> bool:
    """Write .agents/hooks.json. Returns whether .agents/ was created by us."""
    refuse_existing_hooks(repo)
    path = os.path.join(repo, HOOK_FILE)
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


def preflight_agy(model: str, min_quota: float, probe_quota: bool, rundir: str) -> list:
    """Refuses on a missing model or quota; returns warnings."""
    if not shutil.which("agy"):
        raise Refusal("agy nao esta no PATH")
    warns = []
    proc = subprocess.run(["agy", "--version"], capture_output=True, text=True, timeout=60)
    version = proc.stdout.strip().splitlines()[-1].strip() if proc.stdout.strip() else "?"
    if version != TESTED_AGY_VERSION:
        warns.append(f"agy {version}; este script so foi exercitado no {TESTED_AGY_VERSION}. Decisao "
                     "de hook, ferramenta finish, motivos de Stop e formato do /usage podem ter mudado")
    proc = subprocess.run(["agy", "models"], capture_output=True, text=True, timeout=120)
    slugs = parse_models(proc.stdout)
    if proc.returncode != 0 or not slugs:
        raise Refusal(f"`agy models` falhou (rc={proc.returncode}): {tail(proc.stderr.strip(), 300)}")
    if model not in slugs:
        raise Refusal(f"modelo {model!r} nao existe nesta conta. Disponiveis: {', '.join(slugs)}")
    if not probe_quota:
        return warns
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
    return warns


def run_agy(cmd: list, repo: str, rundir: str, timeout_s: int, name: str = "agy", env=None,
            grace: int = 180):
    """Run the worker CLI with cwd = repo and stdin closed (opencode hangs on an
    open stdin pipe). Output goes to <name>.stdout/.stderr in the run dir."""
    out_p, err_p = os.path.join(rundir, f"{name}.stdout"), os.path.join(rundir, f"{name}.stderr")
    with open(out_p, "w") as fo, open(err_p, "w") as fe:
        proc = subprocess.Popen(cmd, cwd=repo, stdout=fo, stderr=fe, stdin=subprocess.DEVNULL,
                                start_new_session=True, env=env)
        try:
            rc = proc.wait(timeout=timeout_s + grace)
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


def trap_signals() -> None:
    """SIGTERM and SIGHUP (closed terminal, dropped ssh/WSL) unwind through the
    `finally` that removes the hooks and kills agy. SIGKILL cannot be trapped;
    refuse_existing_hooks names the leftover file then."""
    for sig in (signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, _sigterm)


# --------------------------------------------------------------------------
# opencode backend: guard plugin outside the tree, external gate loop
# --------------------------------------------------------------------------

# No policy in here: every tool call is forwarded to `agy_worker.py hook
# oc-pre`, and anything but an explicit allow (a crash, no answer) denies.
# A throw in tool.execute.before blocks the call and the model sees the text
# (lab E4, opencode 1.19.0).
OC_GUARD_JS = """// agy-worker guard for opencode, generated for one run; loaded only through
// OPENCODE_CONFIG_CONTENT of that run. The policy is agy_worker.py's.
import { spawnSync } from "node:child_process";
const PY = __PY__, SCRIPT = __SCRIPT__, STATE = __STATE__;
function ask(event, payload) {
  const p = spawnSync(PY, [SCRIPT, "hook", event, "--state", STATE],
                      { input: JSON.stringify(payload), encoding: "utf8", timeout: 120000 });
  try { return JSON.parse(p.stdout); }
  catch { return { decision: "deny", reason: `guard sem resposta (rc=${p.status}) ${String(p.stderr || p.error || "").slice(0, 300)}` }; }
}
export const AgyWorkerGuard = async () => {
  ask("start", {});
  return {
    "tool.execute.before": async (input, output) => {
      const d = ask("oc-pre", { tool: String(input.tool), args: output.args ?? {} });
      if (!d || d.decision !== "allow") throw new Error(`GUARD: ${(d && d.reason) || "negado"}`);
    },
  };
};
"""


def write_oc_guard(rundir: str) -> str:
    path = os.path.join(rundir, "opencode-guard.js")
    js = (OC_GUARD_JS.replace("__PY__", json.dumps(sys.executable))
          .replace("__SCRIPT__", json.dumps(os.path.abspath(__file__)))
          .replace("__STATE__", json.dumps(rundir)))
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(js)
    return path


def opencode_env(guard: str, disable_claude_code: bool) -> dict:
    """The guard plugin and external_directory=deny come in through the
    environment, so nothing is written into the tree or into ~/.config.
    Shell denial lives in the plugin: `permission.bash: deny` makes the free
    models fail at startup (403, lab). ~/.claude/CLAUDE.md is loaded unless
    the task disables it, as for a native subagent."""
    env = {**os.environ, "OPENCODE_DISABLE_AUTOUPDATE": "1", "OPENCODE_DISABLE_SHARE": "1",
           "OPENCODE_CONFIG_CONTENT": json.dumps({
               "plugin": [pathlib.Path(guard).as_uri()],
               "permission": {"external_directory": "deny"}})}
    if disable_claude_code:
        env["OPENCODE_DISABLE_CLAUDE_CODE"] = "1"
    return env


def preflight_opencode(model: str):
    """(binary, warnings); refuses on a missing binary or model. Runs in an
    empty temp dir: from the run dir (inside .git) opencode still found the
    work tree and wrote "$schema" into its opencode.json (lab, 1.19.0)."""
    oc = shutil.which("opencode") or os.path.expanduser("~/.opencode/bin/opencode")
    if not os.access(oc, os.X_OK):
        raise Refusal("opencode nao esta no PATH nem em ~/.opencode/bin")
    with tempfile.TemporaryDirectory(prefix="agy-worker-oc-") as cwd:
        run = lambda *a: subprocess.run([oc, *a], capture_output=True, text=True, timeout=120,  # noqa: E731
                                        cwd=cwd, stdin=subprocess.DEVNULL)
        lines = run("--version").stdout.strip().splitlines()
        proc = run("models")
    version = lines[-1].strip() if lines else "?"
    warns = []
    if version != TESTED_OPENCODE_VERSION:
        warns.append(f"opencode {version}; este script so foi exercitado no {TESTED_OPENCODE_VERSION}. "
                     "Formato dos eventos, plugin e escrita do $schema podem ter mudado")
    models = [ln.strip() for ln in proc.stdout.splitlines() if re.fullmatch(r"\S+/\S+", ln.strip())]
    if proc.returncode != 0 or not models:
        raise Refusal(f"`opencode models` falhou (rc={proc.returncode}): {tail(proc.stderr.strip(), 300)}")
    if model not in models:
        same = [m for m in models if m.split("/")[0] == model.split("/")[0]]
        raise Refusal(f"modelo {model!r} nao existe para o opencode. Do mesmo provider: {', '.join(same) or '-'}")
    return oc, warns


def snapshot_files(repo: str, names) -> dict:
    snap = {}
    for n in names:
        try:
            with open(os.path.join(repo, n), "rb") as fh:
                snap[n] = fh.read()
        except FileNotFoundError:
            snap[n] = None
    return snap


def restore_files(repo: str, snap: dict) -> set:
    """Put back the exact bytes (or absence) of each file; returns what differed."""
    changed = set()
    for n, data in snap.items():
        p = os.path.join(repo, n)
        try:
            with open(p, "rb") as fh:
                cur = fh.read()
        except FileNotFoundError:
            cur = None
        if cur == data:
            continue
        changed.add(n)
        if data is None:
            os.remove(p)
        else:
            with open(p, "wb") as fh:
                fh.write(data)
    return changed


def evaluate_oc(rc, stdout: str, stderr: str):
    """(failures, info) for one `opencode run --format json`. It exits 0 on
    soft denies and on a bogus --agent (lab), so success is read from events:
    no error event, and the last step finished with reason=stop."""
    fails, events = [], []
    if rc == "wrapper-timeout":
        fails.append("timeout: opencode nao terminou e foi encerrado")
    elif rc != 0:
        fails.append(f"opencode saiu com rc={rc}: {tail(stderr.strip(), 400)}")
    for line in stdout.splitlines():
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        if isinstance(ev, dict):
            events.append(ev)
    if not events:
        fails.append("nenhum evento JSON no stdout")
    for ev in events:
        if ev.get("type") == "error":
            err = ev.get("error") or {}
            msg = (err.get("data") or {}).get("message") if isinstance(err, dict) else None
            fails.append(f"evento error: {(msg or json.dumps(err))[:300]}")
    finishes = [ev.get("part") or {} for ev in events if ev.get("type") == "step_finish"]
    if events and (not finishes or finishes[-1].get("reason") != "stop"):
        fails.append("o run nao terminou com reason=stop (ultimo step: "
                     f"{finishes[-1].get('reason') if finishes else 'nenhum'})")
    texts = [(ev.get("part") or {}).get("text", "") for ev in events if ev.get("type") == "text"]
    tokens = {}
    for f in finishes:
        for k, v in (f.get("tokens") or {}).items():
            if isinstance(v, (int, float)):
                tokens[k] = tokens.get(k, 0) + v
    info = {"session": next((ev["sessionID"] for ev in events if ev.get("sessionID")), None),
            "text": texts[-1] if texts else "", "steps": len(finishes), "tokens": tokens,
            "cost": sum(f.get("cost") or 0 for f in finishes),
            "tool_errors": sum(1 for ev in events if ev.get("type") == "tool_use"
                               and ((ev.get("part") or {}).get("state") or {}).get("status") == "error")}
    return fails, info


def extract_report(text: str):
    """The last top-level JSON object in the worker's final message, or None."""
    dec, found, pos = json.JSONDecoder(), None, 0
    text = text or ""
    while (i := text.find("{", pos)) != -1:
        try:
            obj, end = dec.raw_decode(text, i)
        except ValueError:
            pos = i + 1
            continue
        if isinstance(obj, dict):
            found = obj
        pos = end
    return found


def report_problems(report, schema: dict) -> list:
    if not isinstance(report, dict):
        return ["relatorio ausente: a ultima mensagem nao traz um objeto JSON"]
    missing = [k for k in schema.get("required", []) if k not in report]
    return [f"relatorio sem campos obrigatorios: {missing}"] if missing else []


def oc_message(text: str) -> str:
    return "Task:\n" + text if text.lstrip().startswith("-") else text   # never parsed as a flag


def drive_opencode(oc: str, task: dict, repo: str, rundir: str, prompt: str, ctx: dict, saved: dict):
    """run -> gate -> `run -s <session>` with the gate output, up to
    max_gate_attempts runs. opencode has no in-process stop hook (a plugin
    prompting on session.idle did not continue `run`, lab E5), so the loop is
    here. Returns (failures, warnings, report, info)."""
    env = opencode_env(write_oc_guard(rundir), task["disable_claude_code"])
    deadline = time.time() + task["timeout"]
    fails, warns, runs, restored = [], [], [], set()
    sid, report, msg, n = None, None, prompt, task["max_gate_attempts"]
    try:
        for i in range(1, n + 1):
            left = int(deadline - time.time())
            if left < 30:
                fails.append("timeout da task esgotado antes de o gate e o relatorio ficarem prontos")
                break
            cmd = [oc, "run", "--dir", repo, "--format", "json", "-m", task["model"],
                   *(["-s", sid] if sid else []), oc_message(msg)]
            eprint(f"agy-worker: opencode run {i}/{n} ({task['model']}{', sessao ' + sid if sid else ''})…")
            rc, out, err = run_agy(cmd, repo, rundir, left, name=f"opencode-{i}", env=env, grace=0)
            restored |= restore_files(repo, saved)
            run_fails, info = evaluate_oc(rc, out, err)
            sid = sid or info["session"]
            runs.append({"attempt": i, "rc": rc, **{k: v for k, v in info.items() if k != "text"}})
            if run_fails:
                fails += [f"run {i}: {f}" for f in run_fails]
                break
            report = extract_report(info["text"])
            passed, text, _ = gate_cached(rundir, ctx, f"driver:{i}")
            problems = report_problems(report, task["report_schema"])
            if passed and not problems:
                break
            if not sid:
                fails.append("nenhum sessionID nos eventos: nao ha como retomar")
                break
            parts = []
            if not passed:
                parts.append(f"The gate FAILED (attempt {i} of {n}); the task is not done. Fix the real cause, "
                             "without disabling tests, without forbidden shortcuts and without leaving the "
                             f"allowed files. Gate output:\n{tail(text)}")
            if problems:
                parts.append("Your final message must end with the report as ONE JSON object matching the "
                             f"schema given before ({'; '.join(problems)}).")
            msg = "\n\n".join(parts)
    finally:
        restored |= restore_files(repo, saved)
    if restored:
        warns.append(f"o opencode reescreveu {sorted(restored)} (o \"$schema\"); bytes originais restaurados")
    if not fails:
        fails += report_problems(report, task["report_schema"])
    if isinstance(report, dict) and report.get("status") in ("partial", "blocked"):
        fails.append(f"o worker se declarou {report['status']!r}")
    total = {}
    for r in runs:
        for k, v in r.get("tokens", {}).items():
            total[k] = total.get(k, 0) + v
    return fails, warns, report, {"session": sid, "runs": runs, "tokens": total,
                                  "cost": sum(r.get("cost") or 0 for r in runs)}


# --------------------------------------------------------------------------
# subcommands
# --------------------------------------------------------------------------

def base_ctx(repo, task, mode):
    return {
        "mode": mode, "repo": repo, "scope": task["scope"], "side_effects": task["side_effects"],
        "allow_paths": task["allow_paths"], "gate": task["gate"],
        "gate_timeout": task["gate_timeout"], "max_gate_attempts": task["max_gate_attempts"],
        "gate_commands": task["gate"]["format"] + task["gate"]["checks"],
        "deny_patterns": DENY_COMMANDS + (OPENCODE_DENY_COMMANDS if task.get("backend") == "opencode" else [])
        + [(p, "regra do projeto") for p in task["deny_commands"]],
    }


def cmd_delegate(a) -> int:
    trap_signals()
    task = load_task(a.task, backend=a.backend, model=a.model)
    opencode = task["backend"] == "opencode"
    repo = repo_root(a.repo or os.getcwd())
    git(repo, "rev-parse", "--verify", "HEAD")
    dirty = changed_paths(repo)
    if dirty:
        raise Refusal("arvore suja; commite ou guarde antes (o diff do worker tem que ser so dele): "
                      + ", ".join(dirty[:10]))
    if not opencode:
        refuse_existing_hooks(repo)
    rundir = new_rundir(repo, "delegate")
    eprint(f"agy-worker: run dir {rundir}")
    if opencode:
        saved = snapshot_files(repo, OPENCODE_CONFIG_FILES)    # before any opencode process
        try:
            oc, pre_warns = preflight_opencode(task["model"])
        finally:
            if restore_files(repo, saved):
                eprint("agy-worker: o preflight do opencode reescreveu opencode.json; restaurado")
    else:
        pre_warns = preflight_agy(task["model"], task["min_quota"], not a.no_quota_probe, rundir)
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
    integ_before, ignored_before = integrity_state(repo, rundir), ignored_state(repo)
    started = time.time()
    if opencode:
        fails, warns, report, run_info = drive_opencode(oc, task, repo, rundir, prompt, ctx, saved)
        run_info["wall_seconds"] = round(time.time() - started)
    else:
        cmd = ["agy", "-p", prompt, "--model", task["model"], "--output-format", "json",
               "--json-schema", schema_path, "--print-timeout", f"{task['timeout']}s",
               "--dangerously-skip-permissions"]
        created = install_hooks(repo, rundir, ctx)
        try:
            eprint(f"agy-worker: agy rodando ({task['model']}, timeout {task['timeout']}s)…")
            rc, stdout, stderr = run_agy(cmd, repo, rundir, task["timeout"])
        finally:
            remove_hooks(repo, created)
        fails, warns, env = evaluate_run(rc, stdout, stderr, "delegate", task["report_schema"])
        report = env.get("structured_output") if isinstance(env, dict) else None
        run_info = {"rc": rc, "wall_seconds": round(time.time() - started), **(
            {k: env.get(k) for k in ("status", "duration_seconds", "num_turns", "usage", "conversation_id")}
            if isinstance(env, dict) else {})}
    warns = pre_warns + warns
    tampered = diff_state(integ_before, integrity_state(repo, rundir))
    if tampered:
        fails.append("config, hooks ou flags de indice do git, ou o ctx.json do run, mudaram durante o "
                     f"run; o veredito abaixo nao e confiavel: {tampered}")
    events = guard_events(rundir)
    if not any(e.get("event") == "session_start" for e in events):
        fails.append(("o plugin de guard do opencode nao carregou" if opencode else
                      "os hooks do agy-worker nao carregaram") + " (nenhum SessionStart registrado): "
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
    ignored = diff_state(ignored_before, ignored_state(repo))
    if ignored:
        warns.append("arquivos ignorados pelo git criados ou alterados durante o run (o gate pode ter "
                     f"escrito alguns; o resto e escrita fora do escopo que o git status nao mostra): {ignored}")
    leftover = {p: c for p, c in snapshot_procs(repo).items() if p not in before and p != os.getpid()}
    if leftover:
        warns.append("processos novos com cwd no repo ainda vivos (nao foram encerrados): "
                     + "; ".join(f"{p} {c}" for p, c in leftover.items()))
    verdict = {
        "ok": not fails, "mode": "delegate", "backend": task["backend"], "run_dir": rundir,
        "model": task["model"],
        "failures": fails, "warnings": warns, "changed": cls,
        "gate": {"passed": passed, "source": source, "hook_attempts": st.get("attempts", 0),
                 "tail": tail(text, 2500)},
        "guard_denials": [{k: e.get(k) for k in ("tool", "reason", "args")} for e in denials[-20:]],
        "stop_events": [e for e in events if e.get("event") == "stop"],
        "report": report,
        task["backend"]: run_info,
        "next": "Nada foi commitado. Revise `git diff HEAD` contra a fonte da verdade antes de aceitar; "
                "o gate e necessario, nao suficiente.",
    }
    write_json(os.path.join(rundir, "verdict.json"), verdict)
    print(json.dumps(verdict, ensure_ascii=False, indent=2))
    eprint(f"agy-worker: {'OK' if verdict['ok'] else 'FALHOU'} — {len(fails)} falha(s), "
           f"{len(warns)} aviso(s); verdict em {rundir}/verdict.json")
    return 0 if verdict["ok"] else 1


def cmd_review(a) -> int:
    trap_signals()
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
    opencode = a.backend == "opencode"
    model = a.model or (OPENCODE_DEFAULT_MODEL if opencode else DEFAULT_MODEL)
    timeout_s = parse_duration(a.timeout)
    diff_txt = ""
    if a.diff:
        diff_txt = git(repo, "diff", "--no-ext-diff", a.diff)
        if not diff_txt.strip():
            raise Refusal(f"git diff {a.diff} vazio")
        if len(diff_txt.encode()) > MAX_DIFF_BYTES:
            diff_txt = diff_txt.encode()[:MAX_DIFF_BYTES].decode(errors="ignore") + \
                "\n…(diff cortado; leia os arquivos para o resto)…"
    rundir = new_rundir(repo, "review")
    eprint(f"agy-worker: run dir {rundir}")
    if opencode:
        saved = snapshot_files(repo, OPENCODE_CONFIG_FILES)    # before any opencode process
        try:
            oc, pre_warns = preflight_opencode(model)
        finally:
            if restore_files(repo, saved):
                eprint("agy-worker: o preflight do opencode reescreveu opencode.json; restaurado")
    else:
        pre_warns = preflight_agy(model, a.min_quota, not a.no_quota_probe, rundir)
    prompt = question
    if diff_txt:
        prompt += f"\n\n## Diff under review (`git diff {a.diff}`)\n```diff\n{diff_txt}\n```"
    prompt += ("\n\n---\nYou are a read-only reviewer. Do not modify files and do not run commands; "
               f"read files under `{repo}` as needed. Every finding must quote the exact code or text "
               "that supports it in `evidence`. Prefer `unsure` over a guess.\n")
    prompt += report_rule({"backend": a.backend, "report_schema": schema})
    with open(os.path.join(rundir, "prompt.md"), "w", encoding="utf-8") as fh:
        fh.write(prompt)
    # opencode has no plan mode: scope [] denies every write, and every shell
    # command is denied, both by the guard plugin.
    ctx = {"mode": "review", "repo": repo, "scope": [], "side_effects": [], "allow_paths": [],
           "gate": {"format": [], "checks": [], "forbid": []}, "gate_timeout": 60,
           "max_gate_attempts": 0, "gate_commands": [],
           "deny_patterns": REVIEW_DENY_ALL if opencode else DENY_COMMANDS}
    write_json(os.path.join(rundir, "ctx.json"), ctx)
    schema_path = os.path.join(rundir, "review.schema.json")
    write_json(schema_path, schema)
    fp_before, ignored_before = fingerprint(repo, []), ignored_state(repo)
    integ_before = integrity_state(repo, rundir)
    if opencode:
        env_oc = opencode_env(write_oc_guard(rundir), False)
        try:
            eprint(f"agy-worker: review rodando (opencode, {model})…")
            rc, stdout, stderr = run_agy([oc, "run", "--dir", repo, "--format", "json", "-m", model,
                                          oc_message(prompt)], repo, rundir, timeout_s,
                                         name="opencode-1", env=env_oc, grace=0)
        finally:
            restored = restore_files(repo, saved)
        fails, info = evaluate_oc(rc, stdout, stderr)
        report = extract_report(info.pop("text"))
        fails += report_problems(report, schema)
        warns = pre_warns + ([f"o opencode reescreveu {sorted(restored)}; bytes restaurados"] if restored else [])
        run_info = {"rc": rc, **info}
    else:
        cmd = ["agy", "-p", prompt, "--model", model, "--mode", "plan", "--output-format", "json",
               "--json-schema", schema_path, "--print-timeout", f"{timeout_s}s"]
        created = install_hooks(repo, rundir, ctx)
        try:
            eprint(f"agy-worker: review rodando ({model}, --mode plan)…")
            rc, stdout, stderr = run_agy(cmd, repo, rundir, timeout_s)
        finally:
            remove_hooks(repo, created)
        fails, warns, env = evaluate_run(rc, stdout, stderr, "review", schema)
        warns = pre_warns + warns
        report = env.get("structured_output") if isinstance(env, dict) else None
        run_info = {"rc": rc, **({k: env.get(k) for k in ("status", "duration_seconds", "num_turns",
                                                          "usage")} if isinstance(env, dict) else {})}
    if (fingerprint(repo, []) != fp_before or ignored_state(repo) != ignored_before
            or integrity_state(repo, rundir) != integ_before):
        fails.append("a arvore, um arquivo ignorado ou o .git mudou durante um review que devia ser "
                     "somente leitura")
    if not any(e.get("event") == "session_start" for e in guard_events(rundir)):
        if opencode:
            fails.append("o plugin de guard do opencode nao carregou (nenhum SessionStart): o review "
                         "rodou sem nada que o mantivesse somente leitura")
        else:
            warns.append("hooks nao carregaram (nenhum SessionStart): o review rodou so com --mode plan")
    verdict = {"ok": not fails, "mode": "review", "backend": a.backend, "run_dir": rundir, "model": model,
               "failures": fails, "warnings": warns, "report": report, a.backend: run_info,
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
        # tool allowlist: network, workflows, MCP and unknown tools are denied
        for tool in ("read_url_content", "search_web", "run_workflow", "manage_task", "mcp_foo_bar",
                     "ask_permission", "send_message"):
            check(pre(tool, Url="https://example.com/a")["decision"] == "deny", f"{tool} negado")
        # relative escapes in non-shell tools, Cwd, cd, and literal forms
        for args, why in ((("list_dir", {"DirectoryPath": "../.."}), "list_dir .."),
                          (("view_file", {"AbsolutePath": "../../etc/passwd"}), "view_file .."),
                          (("view_file", {"AbsolutePath": "//etc/passwd"}), "view_file //"),
                          (("grep_search", {"SearchPath": "..", "Query": "x"}), "grep_search .."),
                          (("find_by_name", {"SearchDirectory": "../.."}), "find_by_name .."),
                          (("run_command", {"CommandLine": "ls", "Cwd": "/"}), "Cwd /"),
                          (("run_command", {"CommandLine": "ls", "Cwd": "../../../etc"}), "Cwd .."),
                          (("run_command", {"CommandLine": "cd ..&&ls"}), "cd ..&&"),
                          (("run_command", {"CommandLine": "cd / && cat etc/passwd"}), "cd /"),
                          (("run_command", {"CommandLine": "cd && ls"}), "cd sozinho"),
                          (("run_command", {"CommandLine": "cat //etc/passwd"}), "//etc"),
                          (("run_command", {"CommandLine": "cat /*/passwd"}), "glob na raiz"),
                          (("run_command", {"CommandLine": "cat </etc/passwd"}), "redirect de /etc"),
                          (("run_command", {"CommandLine": "echo x>/home/x"}), "redirect para /home")):
            check(pre(args[0], **args[1])["decision"] == "deny", f"escape negado: {why}")
        check(pre("run_command", CommandLine="cd src && ls")["decision"] == "allow", "cd dentro do repo")
        # .git / .agents through the shell, and git global options
        for c in ("printf '[core]\\n\\tfsmonitor = touch X\\n' >> .git/config",
                  "echo x > .git/hooks/pre-commit", "cat src/../.git/config", "ls .agents",
                  "echo '{}' > \"$(git rev-parse --git-path agy-worker)/runs/r/ctx.json\"",
                  "git -c user.name=x commit -m x", "git --no-pager push", "git -C . push",
                  "g''it push origin HEAD", "\"git\" push", "git gc --prune=now", "git pull",
                  "git reflog expire --expire=now --all", "git submodule update --init", "git init sub",
                  "git update-index --assume-unchanged package.json", "git branch -f main HEAD~1",
                  "git config --list", "rm -f -r node_modules", "find . -name '*.log' -delete",
                  "ln -s / src/lnk", "nohup sh -c 'sleep 600' >/dev/null 2>&1 &", "setsid sleep 600 &",
                  "sleep 60 &", "crontab -", "chmod u+s src/a.txt", "echo X=1 > .env",
                  "cat a >> src/a.txt", "npm run deploy", "pnpm nx run web:publish"):
            check(pre("run_command", CommandLine=c)["decision"] == "deny", f"shell negado: {c}")
        # read-only commands that used to be false positives
        for c in ("grep -rn '/api/v1' src", "sed -n '/foo/,/bar/p' src/a.txt", "git grep -n 'deploy' -- src",
                  "git log --grep=publish", "npx vitest run -t 'GET /orders'", "git -C . diff",
                  "git --no-pager log -n 3", "git diff HEAD -- src 2>&1", "grep -n '->' src/a.txt",
                  "npm test >/dev/null 2>&1", "ls .github .gitignore", "python3 -m unittest -v 2>&1 | tail -5",
                  "cat src/a.txt && echo ok"):
            check(pre("run_command", CommandLine=c)["decision"] == "allow", f"leitura permitida: {c}")
        # symlink inside the scope that points out of the repo
        os.symlink("/", os.path.join(repo, "src", "lnk"))
        check(pre("write_to_file", TargetFile=f"{repo}/src/lnk/home/x")["decision"] == "deny", "symlink")
        check(pre("write_to_file", TargetFile="src/lnk/home/x")["decision"] == "deny", "symlink relativo")
        os.remove(os.path.join(repo, "src", "lnk"))
        dctx = dict(ctx, gate_commands=["docker compose run test", "{files}"])
        dpre = lambda c: decide_pre({"toolCall": {"name": "run_command", "args": {"CommandLine": c}}}, dctx)  # noqa: E731
        check(dpre("docker compose run test")["decision"] == "allow", "comando do gate isento")
        check(dpre("docker compose run test && git push")["decision"] == "deny", "encadeado nao e isento")
        check(dpre("docker ps")["decision"] == "deny", "prefixo vazio nao isenta tudo")
        check(dpre("docker compose run test 2>&1 >/dev/null")["decision"] == "allow", "gate com redirect inocuo")
        for c in ("docker compose run test\ngit push origin main", "docker compose run test\rgit push",
                  "docker compose run test <(git push origin HEAD)", "docker compose run test --x $HOME",
                  "docker compose run test > src/../x", "docker compose run testX"):
            check(dpre(c)["decision"] == "deny", f"gate nao isenta: {c!r}")

        # opencode backend: task fields, and its tool calls judged by the same decide_pre
        check(task["backend"] == "agy" and task["model"] == DEFAULT_MODEL, "backend padrao e agy")
        otask = normalize_task({"prompt": "x", "scope": ["src/*"], "backend": "opencode",
                                "gate": {"checks": ["true"]}})
        check(otask["model"] == OPENCODE_DEFAULT_MODEL and not otask["disable_claude_code"],
              "opencode: modelo padrao e CLAUDE.md carregado")
        for bad, why in ((dict(prompt="x", scope=["a"], gate={"checks": ["t"]}, backend="codex"), "backend"),
                         (dict(prompt="x", scope=["*"], gate={"checks": ["t"]}, backend="opencode"),
                          "scope cobre opencode.json"),
                         (dict(prompt="x", scope=["a"], gate={"checks": ["t"]}, disable_claude_code="1"),
                          "disable_claude_code nao booleano")):
            try:
                normalize_task(bad)
                check(False, f"task invalida aceita: {why}")
            except Refusal:
                check(True, why)
        check("ONE JSON object" in compose_prompt(otask, repo) and "ONE JSON object" not in
              compose_prompt(task, repo), "regra do relatorio so no prompt do opencode")
        octx = base_ctx(repo, otask, "delegate")
        oc = lambda tool, **args: decide_oc({"tool": tool, "args": args}, octx)["decision"]  # noqa: E731
        for tool, args, want, why in (
                ("read", {"filePath": f"{repo}/src/a.txt"}, "allow", "read no repo"),
                ("read", {"filePath": "/etc/passwd"}, "deny", "read fora do repo"),
                ("list", {"path": "../.."}, "deny", "list .."),
                ("glob", {"pattern": "/etc/*"}, "deny", "glob absoluto"),
                ("glob", {"pattern": "src/**/*.ts"}, "allow", "glob no repo"),
                ("grep", {"pattern": "/api/v1", "path": "src"}, "allow", "regex do grep nao e caminho"),
                ("write", {"filePath": f"{repo}/src/b.txt", "content": "/etc/x"}, "allow", "write no escopo"),
                ("write", {"filePath": f"{repo}/top.txt", "content": "x"}, "deny", "write fora do escopo"),
                ("edit", {"filePath": "side.json", "oldString": "a", "newString": "b"}, "deny", "edit fora"),
                ("bash", {"command": "echo x > top.txt", "description": "w"}, "deny", "redirect"),
                ("bash", {"command": "printf x >> src/a.txt"}, "deny", "redirect mesmo no escopo"),
                ("bash", {"command": "cp src/a.txt top.txt"}, "deny", "cp no opencode"),
                ("bash", {"command": "cd src && touch x"}, "deny", "touch no opencode"),
                ("bash", {"command": "ls", "workdir": "/"}, "deny", "workdir fora"),
                ("bash", {"command": "python3 -m unittest 2>&1", "description": "Run /etc tests"},
                 "allow", "description nao e caminho"),
                ("bash", {"command": "git commit -m x"}, "deny", "commit"),
                ("apply_patch", {"patchText": "*** Begin Patch\n*** Update File: src/a.txt\n@@\n-a\n+b\n"
                                 "*** End Patch"}, "allow", "patch no escopo"),
                ("apply_patch", {"patchText": "*** Add File: top.txt\n+x\n"}, "deny", "patch fora"),
                ("apply_patch", {"patchText": "*** Update File: src/a.txt\n*** Move to: ../x\n"}, "deny",
                 "patch move para fora"),
                ("apply_patch", {"patchText": "garbage"}, "deny", "patch sem alvo"),
                ("todowrite", {"todos": []}, "allow", "todowrite inerte"),
                ("webfetch", {"url": "https://example.com"}, "deny", "webfetch"),
                ("task", {"prompt": "x", "subagent_type": "general"}, "deny", "subagente"),
                ("batch", {"tool_calls": []}, "deny", "batch"),
                ("brand_new_tool", {}, "deny", "ferramenta desconhecida")):
            check(oc(tool, **args) == want, f"opencode {why}: {tool} {args}")
        check(decide_oc({"tool": "bash", "args": {"command": "cp a b"}}, ctx)["decision"] == "allow",
              "cp continua permitido no agy (politica do agy inalterada)")
        rctx = dict(octx, scope=[], deny_patterns=REVIEW_DENY_ALL)
        check(decide_oc({"tool": "bash", "args": {"command": "ls"}}, rctx)["decision"] == "deny",
              "review opencode nega todo shell")
        check(decide_oc({"tool": "write", "args": {"filePath": "src/a.txt"}}, rctx)["decision"] == "deny",
              "review opencode nega escrita")

        # opencode events: exit 0 is never success
        sid = "ses_x"
        evs = lambda *e: "\n".join(json.dumps(dict(x, sessionID=sid)) for x in e)  # noqa: E731
        fin = lambda r: {"type": "step_finish", "part": {"reason": r, "tokens": {"input": 5, "output": 2},  # noqa: E731
                                                         "cost": 0}}
        txt = {"type": "text", "part": {"text": 'Done.\n```json\n{"status": "done", "x": {"y": 1}}\n```'}}
        f, info = evaluate_oc(0, evs(fin("tool-calls"), txt, fin("stop")), "")
        check(f == [] and info["session"] == sid and info["tokens"]["input"] == 10, f"stream bom: {f}")
        check(extract_report(info["text"]) == {"status": "done", "x": {"y": 1}}, "relatorio de bloco json")
        f, _ = evaluate_oc(0, evs(fin("tool-calls")), "")
        check(any("reason=stop" in x for x in f), "sem stop final reprova")
        f, _ = evaluate_oc(0, evs({"type": "error", "error": {"name": "APIError", "data": {
            "message": "free tier"}}}), "")
        check(any("free tier" in x for x in f), "evento error reprova com exit 0")
        f, _ = evaluate_oc(0, "", "")
        check(any("nenhum evento" in x for x in f), "stdout vazio reprova")
        f, _ = evaluate_oc(1, evs(fin("stop")), "boom")
        check(any("rc=1" in x for x in f), "rc != 0 reprova")
        check(extract_report('{"a": 1} then {"b": {"c": 2}}') == {"b": {"c": 2}}, "ultimo objeto de topo")
        check(extract_report("no json {here") is None, "sem relatorio")
        check(report_problems(None, DEFAULT_REPORT_SCHEMA) and report_problems({"status": "done"},
              DEFAULT_REPORT_SCHEMA), "relatorio ausente ou incompleto")
        check(oc_message("-rf") == "Task:\n-rf" and oc_message("x") == "x", "mensagem nunca vira flag")

        # opencode.json: exact bytes restored, a created one removed
        with open(os.path.join(repo, "opencode.json"), "wb") as fh:
            fh.write(b'{\n  "share": "disabled"\n}\n')
        snap = snapshot_files(repo, OPENCODE_CONFIG_FILES)
        with open(os.path.join(repo, "opencode.json"), "wb") as fh:
            fh.write(b'{\n  "$schema": "https://opencode.ai/config.json",\n  "share": "disabled"\n}\n')
        with open(os.path.join(repo, "opencode.jsonc"), "w") as fh:
            fh.write("{}")
        check(restore_files(repo, snap) == {"opencode.json", "opencode.jsonc"}, "restaura os dois")
        with open(os.path.join(repo, "opencode.json"), "rb") as fh:
            check(fh.read() == b'{\n  "share": "disabled"\n}\n', "bytes originais")
        check(not os.path.exists(os.path.join(repo, "opencode.jsonc")), "criado pelo run e removido")
        check(restore_files(repo, snap) == set(), "restaurar de novo nao muda nada")
        os.remove(os.path.join(repo, "opencode.json"))

        # the generated guard forwards to this script and holds no policy of its own
        grd = os.path.join(tmp, "g")
        os.makedirs(grd)
        js = open(write_oc_guard(grd), encoding="utf-8").read()
        check(json.dumps(os.path.abspath(__file__)) in js and '"oc-pre"' in js and "__" not in js,
              "guard gerado aponta para este script")
        envc = json.loads(opencode_env(os.path.join(grd, "opencode-guard.js"), False)["OPENCODE_CONFIG_CONTENT"])
        check(envc["permission"] == {"external_directory": "deny"} and envc["plugin"][0].startswith("file:///"),
              "config do run: plugin por file:// e external_directory deny")
        check("OPENCODE_DISABLE_CLAUDE_CODE" in opencode_env("/x.js", True)
              and "OPENCODE_DISABLE_CLAUDE_CODE" not in opencode_env("/x.js", False), "flag do CLAUDE.md")

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
        check(hook("oc-pre", {"tool": "write", "args": {"filePath": "/tmp/x", "content": "x"}})["decision"]
              == "deny", "hook oc-pre nega")
        check(hook("oc-pre", {"tool": "read", "args": {"filePath": f"{repo}/src/a.txt"}})
              == {"decision": "allow"}, "hook oc-pre permite explicitamente")
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
        check(hook("oc-pre", {"tool": "read", "args": {}})["decision"] == "deny", "oc-pre quebrado nega")
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
        for bad in ("null", "[]", "3"):
            f, _, _ = evaluate_run(0, bad, "", "delegate", sch)
            check(any("nao um objeto" in x for x in f), f"envelope {bad} reprova")

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

        # what git status cannot see: .git config/hooks/flags, ctx.json, ignored files
        with open(os.path.join(repo, ".gitignore"), "w") as fh:
            fh.write(".env\nbuild/\n")
        subprocess.run(g + ["add", ".gitignore"], check=True)
        subprocess.run(g + ["commit", "-q", "-m", "ignore"], check=True)
        i0, ig0 = integrity_state(repo, rundir), ignored_state(repo)
        os.makedirs(os.path.join(repo, "build"))
        with open(os.path.join(repo, "build", "out.js"), "w") as fh:
            fh.write("x\n")
        check(diff_state(ig0, ignored_state(repo)) == [], "diretorio ignorado novo nao e ruido")
        with open(os.path.join(repo, ".env"), "w") as fh:
            fh.write("X=1\n")
        check(diff_state(ig0, ignored_state(repo)) == [".env"], ".env ignorado detectado")
        check(changed_paths(repo) == [], "e o git status de fato nao o ve")
        subprocess.run(g + ["update-index", "--assume-unchanged", "side.json"], check=True)
        with open(os.path.join(repo, ".git", "config"), "a") as fh:
            fh.write("[core]\n\tfsmonitor = touch FSMON_RAN\n")
        bad = diff_state(i0, integrity_state(repo, rundir))
        changed_paths(repo)
        check(any(b.endswith("config") for b in bad) and "<assume-unchanged/skip-worktree>" in bad,
              f"config e flag de indice detectados: {bad}")
        check(not os.path.exists(os.path.join(repo, "FSMON_RAN")), "fsmonitor plantado nao roda no git do script")
        subprocess.run(["git", "-C", repo, "config", "--unset", "core.fsmonitor"], check=True)
        subprocess.run(g + ["update-index", "--no-assume-unchanged", "side.json"], check=True)
        os.remove(os.path.join(repo, ".env"))
        shutil.rmtree(os.path.join(repo, "build"))

        # a timed-out gate command takes its children with it
        t0 = time.time()
        ok, text, _ = run_gate(repo, dict(ctx, gate_timeout=1, gate=dict(ctx["gate"], format=[],
                                          checks=["sleep 30 & sleep 30; wait"])), baseline=True)
        check(not ok and "rc=timeout" in text and time.time() - t0 < 15, "timeout do gate")
        created = install_hooks(repo, rundir, ctx)
        spec = read_json(os.path.join(repo, HOOK_FILE))
        check(set(spec["agy-worker"]) == {"SessionStart", "PreToolUse", "Stop"}, "hooks.json gerado")
        check(changed_paths(repo) == [], "hooks.json nao conta como mudanca")
        try:
            install_hooks(repo, rundir, ctx)
            check(False, "sobrescreveu hooks.json existente")
        except Refusal as exc:
            check("sobra de um run" in str(exc) and "rm " in str(exc), "reconhece a propria sobra")
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
    d.add_argument("--backend", choices=BACKENDS, help="sobrepoe o campo backend da task")
    d.add_argument("--repo")
    d.add_argument("--no-quota-probe", action="store_true", help="so agy")
    r = sub.add_parser("review", help="segunda opiniao somente leitura (--mode plan)")
    r.add_argument("prompt", nargs="*")
    r.add_argument("--prompt-file")
    r.add_argument("--diff", help="intervalo para `git diff`, ex.: HEAD~1 ou main...HEAD")
    r.add_argument("--schema")
    r.add_argument("--model")
    r.add_argument("--backend", choices=BACKENDS, default="agy")
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
    h.add_argument("event", choices=["pre", "stop", "start", "oc-pre"])
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
