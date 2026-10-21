#!/usr/bin/env python3
"""crew: run an agent CLI (agy, opencode or copilot) headless as a guarded worker.

Claude plans and reviews; agy executes one well-scoped slice. This script is
the guard rail between them. Subcommands:

  delegate TASK.json   run the task under agy with guard hooks and a gate
  review [PROMPT...]   read-only second opinion (agy: --mode plan + --json-schema)
  gate TASK.json       run the task's gate by hand (--baseline: commands only)
  hook pre|stop|start  agy workspace hook handlers (installed per run)
  hook oc-pre          the opencode guard plugin's handler (same policy)
  hook cp-pre|cp-stop  GitHub Copilot CLI repo hooks (same policy, gate on agentStop)
  --self-test          exercises everything that does not need agy itself

Why each check exists is in the plugin README; the short version is that agy
1.3.4 reports success in most of the ways it fails (measured, n=1 each):
timeouts, denied actions and an unsatisfied --json-schema all exit 0, a
PreToolUse hook printing `{}` denies the call, and --sandbox confines nothing.
So nothing here trusts the exit code, and every hook prints an explicit
decision even when it crashes.

The agy backend also watches the run: agy (1.3.4, still on 1.4.2) moves long
commands to a background task whatever WaitMsBeforeAsync says and then waits up
to 30 min for them (15 min logged on 1.4.2), so BackgroundWatcher ends the
worker's leftovers once it finished green.

Stdlib only. State lives in `$(git rev-parse --git-path crew)` (`agy-worker`
before 0.4.0), so a run
never dirties the work tree; the only file written into the tree is
`.agents/hooks.json`, for the duration of the run, and it is removed after.

Second backend, `"backend": "opencode"` in the task (opencode 1.19.0): the
guard is an opencode plugin generated in the run dir and loaded only through
that run's OPENCODE_CONFIG_CONTENT; it forwards every tool call to `hook
oc-pre`, which translates it and asks the same decide_pre. opencode has no
stop hook and no --json-schema, so the gate loop (run, gate, `run -s` with the
gate output) and the report parsing are here, and opencode.json's bytes are
restored after every opencode process (it writes "$schema" into it).

Third backend, `"backend": "copilot"` (GitHub Copilot CLI 1.0.96, Free plan,
`--model auto` only): repo hooks in `.github/hooks/crew-<run>.json`,
loaded only because the run sets COPILOT_ALLOW_ALL=true, forward every tool
call to `hook cp-pre` (same decide_pre) and run the gate on agentStop. The
shell and subagents are removed from the model (`--excluded-tools bash task`),
so every command of the gate runs here, never by the worker.
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
STATE_NAME = "crew"
DEFAULT_MODEL = "gemini-3.8-flash-high"
DEFAULT_TIMEOUT = "30m"
DEFAULT_REVIEW_TIMEOUT = "15m"
DEFAULT_GATE_TIMEOUT = 900
DEFAULT_MAX_GATE_ATTEMPTS = 5
DEFAULT_MIN_QUOTA = 0.05
TESTED_AGY_VERSION = "1.4.4"       # every agy behaviour this script relies on was seen on this one
MAX_PROMPT_BYTES = 100_000          # one argv string is capped at 128 KiB on Linux
MAX_DIFF_BYTES = 60_000
TAIL_CHARS = 6000
# Basenames a worker may not read or write, by tool or by shell. Not distrust
# of the model: what it reads goes to the provider's servers, and a password in
# a training corpus can only be fixed by rotating it. A task can replace the
# list, or pass [] to turn it off.
DEFAULT_SECRET_GLOBS = [".env", ".env.*", ".dev.vars", ".dev.vars.*", "*.pem", "*.key", "*.p12",
                        "*.pfx", "id_rsa*", "id_ed25519*", "id_ecdsa*", "id_dsa*"]
SECRET_EXCEPTIONS = ("*.example", "*.sample", "*.template")
# Every process of a run inherits this marker, so the ones it leaves behind
# (an Nx daemon reparents to init and keeps no ancestry) can be found and
# stopped without touching anything the user started.
RUN_ENV = "CREW_RUN"
WORKER_ENV = {"NX_DAEMON": "false"}
BACKENDS = ("agy", "opencode", "copilot")
OPENCODE_DEFAULT_MODEL = "opencode/longcat-2.5-preview-free"
# opencode 2.x dropped `--dir` (the run uses cwd = repo) and by default attaches
# to a shared background service, which would not see this process's
# OPENCODE_CONFIG_CONTENT and so would run without the guard plugin.
# `--standalone` starts a private server that ends with the run.
OC_RUN_FLAGS = ["--standalone"]
TESTED_OPENCODE_VERSION = "1.19.0"
# opencode writes "$schema" into these, in the process cwd, on every run (seen
# on 1.19.0 even with --dir); the driver restores their bytes after each run.
OPENCODE_CONFIG_FILES = ("opencode.json", "opencode.jsonc")
# GitHub Copilot CLI. Everything here was seen on 1.0.96 with a Free account
# (scratchpad lab, 2026-10-13, n=1 per case), where only `--model auto` is
# accepted and it routes to gpt-5.6-luna.
TESTED_COPILOT_VERSION = "1.0.96"
COPILOT_DEFAULT_MODEL = "auto"
COPILOT_HOOK_DIR = ".github/hooks"
COPILOT_HOOK_PREFIX = "crew-"
COPILOT_MAX_STOP_BLOCKS = 8          # the CLI overrides agentStop after 8 consecutive blocks (docs)
COPILOT_MIN_AI_CREDITS = 30          # `--max-ai-credits` refuses less: a runaway backstop, not a budget
COPILOT_REPORT_ASKS = 2              # extra agentStop blocks asking only for the missing report
# agy: extra Stop `continue`s asking for `finish` when the gate is green but the
# worker stopped without calling it. Seen in the lab (2026-10-13, n=1): the
# background-task notice tells the model to end the turn, it did, and the
# envelope came back with structured_output null although the gate was green.
AGY_REPORT_ASKS = 2
# Both, always: excluding only `bash` sent the model into 2826 `task`
# subagent calls (~5.5 AI credits) in the lab.
COPILOT_EXCLUDED_TOOLS = ["bash", "task"]
COPILOT_REVIEW_EXCLUDED_TOOLS = COPILOT_EXCLUDED_TOOLS + ["apply_patch"]
# Tool names seen in the lab that run or inspect a shell; any of them in the
# event stream fails the run, and the hook denies them anyway.
COPILOT_SHELL_TOOLS = {"bash", "write_bash", "read_bash", "stop_bash", "list_bash", "shell", "powershell"}
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

# agy 1.4.4 renamed its file tools (smoke 2026-10-21). They are translated to
# the names above before any check, so path, scope and secret rules apply
# unchanged; without this the guard denied them and the worker edited through
# the shell instead.
AGY_RENAMED = {
    "read_file": ("view_file", {"Path": "AbsolutePath"}),
    "write_file": ("write_to_file", {"Path": "TargetFile", "Content": "CodeContent"}),
    "edit_file": ("replace_file_content", {"Path": "TargetFile", "Target": "TargetContent",
                                           "Replacement": "ReplacementContent"}),
}

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
# Copilot CLI tool -> (agy tool, {copilot arg: agy arg}). `view`, `glob` and
# `apply_patch` (a raw patch string, not JSON) were seen in the lab; `grep`,
# `create` and `edit` are the CLI's documented file tools, mapped the same way.
CP_TOOLS = {
    "view": ("view_file", {"path": "AbsolutePath"}),
    "glob": ("find_by_name", {"path": "SearchDirectory", "pattern": "Pattern"}),
    "grep": ("grep_search", {"path": "SearchPath", "pattern": "Query", "glob": "Includes"}),
    "create": ("write_to_file", {"path": "TargetFile", "file_text": "CodeContent", "content": "CodeContent"}),
    "edit": ("replace_file_content", {"path": "TargetFile", "old_str": "TargetContent",
                                      "new_str": "ReplacementContent"}),
    "str_replace": ("replace_file_content", {"path": "TargetFile", "old_str": "TargetContent",
                                             "new_str": "ReplacementContent"}),
}
# Where Copilot loads hooks from inside a repo (hooks reference). A worker
# that could write there could replace its own guard, so no scope may cover
# them and the hook denies writes to them whatever the scope says.
COPILOT_HOOK_PREFIXES = (".github/hooks/", ".github/copilot/", ".claude/")
COPILOT_HOOK_SAMPLES = (".github/hooks/crew-x.json", ".github/copilot/settings.json",
                        ".github/copilot/settings.local.json", ".claude/settings.json",
                        ".claude/settings.local.json")
CP_INERT_TOOLS = {"report_intent", "think", "update_todo"}   # no file or process effect
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
    for key in ("side_effects", "allow_paths", "deny_commands", "secret_globs"):
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
    if not isinstance(task.get("copilot_model_override", False), bool):
        errs.append("copilot_model_override deve ser booleano")
    max_attempts = task.get("max_gate_attempts", DEFAULT_MAX_GATE_ATTEMPTS)
    credits = task.get("max_ai_credits", COPILOT_MIN_AI_CREDITS)
    if not isinstance(credits, (int, float)) or isinstance(credits, bool) or credits < COPILOT_MIN_AI_CREDITS:
        errs.append(f"max_ai_credits deve ser numero >= {COPILOT_MIN_AI_CREDITS} (minimo do copilot)")
    if backend == "copilot":
        model_err = copilot_model_problem(task.get("model", COPILOT_DEFAULT_MODEL),
                                          task.get("copilot_model_override", False))
        if model_err:
            errs.append(model_err)
        if isinstance(max_attempts, (int, str)) and str(max_attempts).isdigit() and \
                int(max_attempts) > COPILOT_MAX_STOP_BLOCKS:
            errs.append(f"max_gate_attempts {max_attempts} > {COPILOT_MAX_STOP_BLOCKS}: o copilot ignora o "
                        f"agentStop depois de {COPILOT_MAX_STOP_BLOCKS} bloqueios seguidos")
        if isinstance(scope, list) and any(in_globs(f, scope) for f in COPILOT_HOOK_SAMPLES):
            errs.append("scope do copilot cobre um arquivo de onde o copilot carrega hooks "
                        "(.github/hooks/, .github/copilot/settings*.json, .claude/settings*.json)")
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
        "model": task.get("model", {"opencode": OPENCODE_DEFAULT_MODEL,
                                    "copilot": COPILOT_DEFAULT_MODEL}.get(backend, DEFAULT_MODEL)),
        "copilot_model_override": task.get("copilot_model_override", False),
        "max_ai_credits": credits,
        "timeout": parse_duration(task.get("timeout", DEFAULT_TIMEOUT)),
        "gate_timeout": parse_duration(task.get("gate_timeout", DEFAULT_GATE_TIMEOUT)),
        "max_gate_attempts": int(task.get("max_gate_attempts", DEFAULT_MAX_GATE_ATTEMPTS)),
        "side_effects": list(task.get("side_effects", [])),
        "allow_paths": list(task.get("allow_paths", [])),
        "deny_commands": list(task.get("deny_commands", [])),
        "secret_globs": list(task.get("secret_globs", DEFAULT_SECRET_GLOBS)),
        "min_quota": float(task.get("min_quota", DEFAULT_MIN_QUOTA)),
    }


def copilot_model_problem(model, override: bool):
    """None when the model may be used with Copilot, else why not."""
    if model == COPILOT_DEFAULT_MODEL:
        return None
    if override and isinstance(model, str) and model:
        return None
    return (f"copilot: modelo {model!r} recusado. Nesta conta (plano Free, copilot 1.0.96, 2026-10-13) so "
            "`--model auto` funcionou: os 32 modelos do catalogo foram recusados com `--model`, e o Auto "
            "roteou sempre para gpt-5.6-luna. Num plano pago, `\"copilot_model_override\": true` na task (ou "
            "--copilot-model-override no review) libera outro modelo: caminho NAO testado.")


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
    if task.get("backend") == "copilot":
        run_yourself = ("You have NO shell tool: do not try to run commands, tests or formatters. When you "
                        "stop, this gate runs automatically and, if it fails, you are shown its output and "
                        "must continue.")
    else:
        run_yourself = "Run the format and check commands yourself before declaring done."
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
  {note}{run_yourself} The gate is fully described here; do not search the filesystem for it.
- Final report: fill every field of the required schema. List every behaviour divergence you introduced and why. Do not claim a check passed unless you saw it pass.
{report_rule(task)}"""


def report_rule(task: dict) -> str:
    """opencode has no --json-schema: the report is the last JSON object in
    the final message, and the driver asks again if it is missing."""
    if task.get("backend") not in ("opencode", "copilot"):
        return ""
    again = (" Every final message, including the one after gate feedback, must end with it."
             if task.get("backend") == "copilot" else "")
    return ("- End your final message with the report as ONE JSON object (no prose after it) matching "
            f"this JSON schema: {json.dumps(task['report_schema'], separators=(',', ':'))}.{again}\n")


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


def secret_reason(what: str) -> str:
    return (f"Arquivo de segredo bloqueado: {what}. O worker nao le nem escreve .env, chaves ou "
            "certificados; se a tarefa precisa de um valor de config, diga no relatorio "
            "(out_of_scope_needs).")


def deny(reason: str) -> dict:
    return {"decision": "deny", "reason": reason}


def is_secret(path: str, globs) -> bool:
    name = os.path.basename(path.rstrip("/"))
    if not name or any(fnmatch.fnmatch(name, e) for e in SECRET_EXCEPTIONS):
        return False
    return any(fnmatch.fnmatch(name, g) for g in globs)


SHELL_WORDS = re.compile(r"[^\s;&|()<>`'\"=]+")


def allow_cmd(ctx: dict) -> dict:
    """Plain allow. Overwriting WaitMsBeforeAsync does NOT keep run_command in
    the foreground: on agy 1.3.4 the overwrite was applied ("A pre-tool hook
    changed the arguments ... Changed: WaitMsBeforeAsync") and a long `nx run
    web:typecheck` still went to a background task after ~4 s (two LOTVS runs,
    2026-10-13). The leftover background task is what kept agy alive for 11 and
    16 min after the worker stopped; BackgroundWatcher handles that instead."""
    return {"decision": "allow"}


def decide_pre(payload: dict, ctx: dict) -> dict:
    """Decision for every tool call except the gate on `finish`. Always explicit."""
    call = payload.get("toolCall") or {}
    name = call.get("name", "")
    args = call.get("args") or {}
    if not isinstance(args, dict):
        args = {}
    if name in AGY_RENAMED:
        name, keys = AGY_RENAMED[name]
        args = {keys.get(k, k): v for k, v in args.items()}
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
        if (key.endswith(("Path", "File", "Paths", "Files")) or val.startswith(("/", "~", "."))
                or "/" in val) and is_secret(val, ctx.get("secret_globs", [])):
            return deny(secret_reason(val))
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
        for word in SHELL_WORDS.findall(cmd):
            if is_secret(word, ctx.get("secret_globs", [])):
                return deny(secret_reason(word))
        if is_gate_command(cmd, ctx.get("gate_commands", [])):
            return allow_cmd(ctx)
        bare = unquote_shell(cmd)
        for pat, label in ctx.get("deny_patterns", []):
            if re.search(pat, cmd) or re.search(pat, bare):
                return deny(f"Comando bloqueado ({label}): {cmd!r}. Edite so com as ferramentas de edicao; "
                            "sem commit, push, install, deploy, migracao, rede ou processos. Testes, lint, "
                            "typecheck e leitura sao permitidos.")
        if writes_by_redirect(cmd):
            return deny(f"Escrita pelo shell bloqueada (redirecionamento para arquivo): {cmd!r}. Use as "
                        "ferramentas de edicao; redirecione saida so para /dev/null ou 2>&1.")
        return allow_cmd(ctx)
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


def cp_calls(tool: str, args) -> list:
    """A Copilot tool call as agy-shaped payloads for decide_pre, like
    oc_calls. `apply_patch` arrives as the raw patch text (lab); one payload per
    file it touches. Unknown tools keep their name, so the allowlist denies."""
    if tool in CP_INERT_TOOLS:
        return []
    if isinstance(args, str):
        try:
            parsed = json.loads(args)
        except ValueError:
            parsed = None
        args = parsed if isinstance(parsed, dict) else {"_raw": args}
    if not isinstance(args, dict):
        args = {}
    if tool == "apply_patch":
        text = "\n".join(v for v in args.values() if isinstance(v, str))
        targets = PATCH_TARGET.findall(text)
        return ([{"toolCall": {"name": "write_to_file", "args": {"TargetFile": t}}} for t in targets]
                or [{"toolCall": {"name": "apply_patch", "args": {}}}])
    name, keys = CP_TOOLS.get(tool, (tool, {}))
    mapped = {keys.get(k, "Description" if k in ("description", "intent") else k): v
              for k, v in args.items()}
    return [{"toolCall": {"name": name, "args": mapped}}]


def decide_cp(payload: dict, ctx: dict) -> dict:
    """preToolUse for Copilot. The shell is excluded from the model; if a shell
    tool shows up anyway it is denied here, before decide_pre could allow a
    harmless-looking command, and the verdict fails the run."""
    tool = str(payload.get("toolName", ""))
    if tool in COPILOT_SHELL_TOOLS:
        return deny(f"Ferramenta {tool} bloqueada: este worker nao tem shell. Edite com as ferramentas "
                    "de arquivo; o gate roda sozinho quando voce para.")
    for call in cp_calls(tool, payload.get("toolArgs")):
        target = (call["toolCall"].get("args") or {}).get("TargetFile")
        if isinstance(target, str) and target:
            rel = os.path.relpath(resolve(target, ctx["repo"]), ctx["repo"])
            if rel.startswith(COPILOT_HOOK_PREFIXES):
                return deny(f"Escrita bloqueada em {rel}: o copilot carrega hooks dali.")
        out = decide_pre(call, ctx)
        if out["decision"] != "allow":
            return out
    return {"decision": "allow"}


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

def changed_paths(repo: str, ignore=()) -> list:
    """Changed and untracked paths, minus agy's hooks file and `ignore` (the
    exact Copilot hooks file of the run, never a glob)."""
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
    skip = {HOOK_FILE, *ignore}
    return [p for p in dict.fromkeys(paths) if p not in skip]


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


def fingerprint(repo: str, side_effects, ignore=()) -> str:
    h = hashlib.sha256()
    tracked = set(git(repo, "ls-files", "-z").split("\0"))
    for p in sorted(changed_paths(repo, ignore)):
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
    cls = classify(changed_paths(repo, ctx.get("ignore_paths", [])), ctx["scope"],
                   ctx.get("side_effects", []))
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
            # CREW_GATE lets a command tell the gate run from the worker's own
            # run of the same command (AGY_WORKER_GATE: the pre-0.4.0 name). Own session, so a timeout
            # kills the whole tree the command started, not just bash.
            proc = subprocess.Popen(["bash", "-c", cmd], cwd=repo, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, text=True, start_new_session=True,
                                    env={**os.environ, **WORKER_ENV, "CREW_GATE": "1", "AGY_WORKER_GATE": "1",
                                         RUN_ENV: ctx.get("run_id", "")})
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
    fp = fingerprint(repo, ctx.get("side_effects", []), ctx.get("ignore_paths", []))
    if st.get("fingerprint") == fp and st.get("passed") is True:
        passed, text, cached = True, st["text"], True
    else:
        passed, text, _ = run_gate(repo, ctx)
        st["runs"] += 1
        with open(os.path.join(rundir, f"gate-{st['runs']}.log"), "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
        # Gate commands can themselves touch the tree (formatters, Nx config);
        # the cache key is the state *after* them, so an identical re-check hits.
        fp = fingerprint(repo, ctx.get("side_effects", []), ctx.get("ignore_paths", []))
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
        elif event == "cp-pre":
            out = decide_cp(payload, ctx)
            entry = {"event": "pre", "tool": payload.get("toolName"), "decision": out["decision"]}
            if out["decision"] != "allow":
                entry["reason"] = out.get("reason", "")[:300]
                args = payload.get("toolArgs")
                entry["args"] = ({k: (v if len(str(v)) < 300 else str(v)[:300] + "…")
                                  for k, v in args.items() if k not in ("file_text", "old_str", "new_str")}
                                 if isinstance(args, dict) else str(args)[:300])
            append_jsonl(log, entry)
        elif event == "cp-stop":
            out = cp_stop(rundir, ctx, payload)
            append_jsonl(log, {"event": "stop", "reason": "agentStop",
                               "stop_hook_active": payload.get("stop_hook_active"),
                               "decision": out["decision"]})
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
                prior = guard_events(rundir)
                finished = any(e.get("event") == "pre" and e.get("tool") in FINISH_TOOLS
                               and e.get("decision") == "allow" for e in prior)
                asks = sum(1 for e in prior if e.get("event") == "stop" and e.get("ask") == "report")
                if passed and not finished and asks < AGY_REPORT_ASKS:
                    out = {"decision": "continue", "reason":
                           "O gate PASSOU. Falta so o relatorio: chame a ferramenta finish agora, com o "
                           "relatorio pedido. Nao espere comando em segundo plano nem rode mais nada."}
                    append_jsonl(log, {"event": "stop", "reason": reason, "decision": "continue",
                                       "ask": "report"})
                    print(json.dumps(out, ensure_ascii=False))
                    return 0
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
               if event in ("pre", "oc-pre", "cp-pre") else {"decision": "stop"} if event == "stop"
               else {"decision": "allow"} if event == "cp-stop" else {})
    print(cp_hook_output(event, out) if event in ("cp-pre", "cp-stop") else json.dumps(out, ensure_ascii=False))
    return 0


def cp_hook_output(event: str, out: dict) -> str:
    """Copilot's hook contract. preToolUse: a deny is `permissionDecision`
    with a reason (lab: the model sees "Denied by preToolUse hook: <reason>");
    an allow prints nothing, the lab-verified pass-through, so the CLI's own
    path checks (`--disallow-temp-dir`) still apply. agentStop: `block` with
    the reason as the next prompt, or `allow`."""
    if event == "cp-pre":
        if out.get("decision") == "allow":
            return ""
        return json.dumps({"permissionDecision": "deny",
                           "permissionDecisionReason": out.get("reason") or "negado"}, ensure_ascii=False)
    if out.get("decision") == "block":
        return json.dumps({"decision": "block", "reason": out.get("reason", "")}, ensure_ascii=False)
    return json.dumps({"decision": "allow"})


def cp_final_text(stdout: str):
    """The content of the last non-empty assistant.message in Copilot's JSONL,
    or None when there is none."""
    text = None
    for line in stdout.splitlines():
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        if isinstance(ev, dict) and ev.get("type") == "assistant.message":
            content = (ev.get("data") or {}).get("content")
            if isinstance(content, str) and content.strip():
                text = content
    return text


def cp_stop(rundir: str, ctx: dict, payload: dict) -> dict:
    """agentStop: the gate, then the report. The worker has no shell, so this
    is the only place the gate runs before the final one. Blocks only while
    the gate fails (up to max_gate_attempts) or, once green, while the final
    message visibly lacks the report (up to COPILOT_REPORT_ASKS); when the
    event stream cannot be read yet, the report is not asked for, so a
    buffering CLI cannot loop the worker."""
    if ctx.get("mode") != "delegate":
        return {"decision": "allow"}
    passed, text, n = gate_cached(rundir, ctx, "agentStop")
    if not passed:
        if n >= ctx["max_gate_attempts"]:
            return {"decision": "allow"}
        return {"decision": "block", "reason":
                f"The gate FAILED (attempt {n} of {ctx['max_gate_attempts']}); the task is not done. Fix the "
                "real cause with the file tools, without disabling tests, without forbidden shortcuts and "
                "without leaving the allowed files. You have no shell: the gate runs again when you stop. "
                "End your final message with the JSON report. Gate output:\n" + tail(text)}
    try:
        with open(ctx.get("events_file", ""), encoding="utf-8", errors="replace") as fh:
            final = cp_final_text(fh.read())
    except OSError:
        final = None
    problems = report_problems(extract_report(final), ctx.get("report_schema") or DEFAULT_REPORT_SCHEMA)
    if final is None or not problems:
        return {"decision": "allow"}
    asks_path = os.path.join(rundir, "report-asks.json")
    asks = read_json(asks_path, {"n": 0})
    if asks["n"] >= COPILOT_REPORT_ASKS:
        return {"decision": "allow"}
    asks["n"] += 1
    write_json(asks_path, asks)
    return {"decision": "block", "reason":
            "The gate passed. Now end your final message with the report as ONE JSON object matching the "
            f"schema given before ({'; '.join(problems)}). Do not change any file."}


# --------------------------------------------------------------------------
# agy invocation and result evaluation
# --------------------------------------------------------------------------

def parse_models(text: str) -> list:
    return [ln.split("\t", 1)[0].strip() for ln in text.splitlines()
            if "\t" in ln and ln.split("\t", 1)[0].strip()]


EFFORT_SUFFIXES = {"low", "medium", "high", "xhigh", "max"}


def quota_groups_for(groups: list, model: str) -> list:
    """The /usage groups that meter `model`. The family alone ("gemini") is too
    wide since agy 1.4.2: "Gemini 4 Argon" is its own group next to "Gemini
    Models" (Flash, Pro), and on a Pro plan the two are separate quotas, so an
    exhausted Argon must not refuse a Flash run nor the reverse. Match on the
    model line first (flash, argon, sonnet, oss), the family only as fallback."""
    def text(g):
        return (str(g.get("name", "")) + " " + str(g.get("description", ""))).lower()
    parts = model.lower().split("-")
    lines = [p for p in parts[1:] if p not in EFFORT_SUFFIXES and not any(c.isdigit() for c in p)]
    hits = [g for g in groups if any(re.search(rf"\b{re.escape(p)}\b", text(g)) for p in lines)]
    return hits or [g for g in groups if parts[0] in text(g)]


def evaluate_quota(envelope: dict, model: str, min_quota: float):
    """None when there is headroom, else a refusal message."""
    groups = (((envelope or {}).get("command") or {}).get("data") or {}).get("groups")
    if not isinstance(groups, list):
        return "nao consegui ler os grupos de quota de `agy -p /usage --output-format json`"
    family = model.split("-", 1)[0].lower()
    hits = quota_groups_for(groups, model)
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


def proc_cmdline(pid: int, limit: int = 200) -> str:
    """Display form; pass limit=0 for the whole thing (matching must not see a
    truncated line: a long script path pushed `crew.py hook` past 200 chars)."""
    with open(f"/proc/{pid}/cmdline", "rb") as fh:
        text = fh.read().replace(b"\0", b" ").decode(errors="replace").strip()
    return text[:limit] if limit else text


def proc_env_has(pid: int, *entries: bytes) -> list:
    """Which of `entries` (b"KEY=value") are in the process environment."""
    with open(f"/proc/{pid}/environ", "rb") as fh:
        env = set(fh.read().split(b"\0"))
    return [e in env for e in entries]


def ppid_map() -> dict:
    """pid -> parent pid, for every process we can see."""
    out = {}
    for pid in os.listdir("/proc"):
        if not pid.isdigit():
            continue
        try:
            with open(f"/proc/{pid}/stat", "rb") as fh:
                # comm may contain spaces and parens: the fields after the last ')'
                out[int(pid)] = int(fh.read().rsplit(b")", 1)[1].split()[1])
        except (OSError, IndexError, ValueError):
            continue
    return out


def descendants(root: int, ppids: dict) -> dict:
    """pid -> parent pid for every descendant of root (root excluded)."""
    children = {}
    for pid, pp in ppids.items():
        children.setdefault(pp, []).append(pid)
    out, todo = {}, [root]
    while todo:
        for c in children.get(todo.pop(), []):
            if c not in out and c != root:
                out[c] = ppids[c]
                todo.append(c)
    return out


def marked_procs(run_id: str) -> dict:
    """pid -> cmdline for every process carrying this run's marker, except us."""
    if not run_id:
        return {}
    marker, me, hits = f"{RUN_ENV}={run_id}".encode(), os.getpid(), {}
    for pid in os.listdir("/proc"):
        if not pid.isdigit() or int(pid) == me:
            continue
        try:
            if proc_env_has(int(pid), marker)[0]:
                hits[int(pid)] = proc_cmdline(int(pid))
        except OSError:
            continue
    return hits


def kill_pids(pids) -> None:
    """SIGTERM, 5 s, then SIGKILL whatever is left. Callers pass only pids they
    proved are ours (the run marker)."""
    for sig in (signal.SIGTERM, signal.SIGKILL):
        alive = []
        for pid in pids:
            try:
                os.kill(pid, sig)
                alive.append(pid)
            except OSError:
                pass
        deadline = time.time() + 5
        while alive and time.time() < deadline:
            alive = [p for p in alive if os.path.exists(f"/proc/{p}")]
            time.sleep(0.2)
        if not alive:
            break


def stop_run_procs(run_id: str) -> dict:
    """Stop the processes that carry this run's marker and outlived it (pid ->
    cmdline). Only our own: the marker is set by this script on the worker and
    on the gate, and descendants inherit it even after reparenting."""
    hits = marked_procs(run_id)
    kill_pids(list(hits))
    return hits


# Names an MCP server by its command line (`uv tool uvx ... kino --mcp`,
# `npx -y @upstash/context7-mcp`, `mcp-server-x`). A second line of defence
# behind the baseline in BackgroundWatcher, for a server agy starts late.
MCP_CMDLINE = re.compile(r"(?i)(\bmcp\b|mcp[-_]?server|[-_]mcp\b)")
BG_GRACE_S = 15


class BackgroundWatcher:
    """Ends the worker's leftover background commands so agy can exit.

    agy 1.3.4 moves a long run_command (an `nx run web:typecheck`) to a
    background task after ~4 s whatever WaitMsBeforeAsync says, and after the
    root agent is done it logs "waiting up to 30m0s for N background task(s)"
    and sits there: 16 and 11 min in two LOTVS runs (2026-10-13), until the
    orphans were killed by hand; then agy exited 0 with a valid envelope.

    Polled once a second while agy runs. Once guard.jsonl shows the worker is
    done after a GREEN gate (Stop answered `stop`, or `finish` allowed), it
    waits BG_GRACE_S and then terminates processes that are all of:
      - descendants of the agy process, and never agy itself (its stdout
        envelope is the verdict's input);
      - carrying this run's marker (CREW_RUN=<run id>) in their environment;
      - not a hook process of ours or anything under one (the gate runs there,
        with CREW_GATE=1, also skipped);
      - not in the baseline: everything agy had started before the worker's
        first allowed run_command (MCP servers, agy's own helpers), and their
        subtrees; nor anything whose command line names an MCP server.
    Whatever is killed is recorded and goes into the verdict.
    """

    def __init__(self, rundir: str, run_id: str, grace: float = BG_GRACE_S):
        self.rundir, self.grace = rundir, grace
        self.marker = f"{RUN_ENV}={run_id}".encode()
        self.hook_tag = f"{os.path.abspath(__file__)} hook"
        self.baseline: set = set()
        self.saw_command = False
        self.gate_green = False
        self.finished_at = None
        self.offset = 0
        self.seen: set = set()
        self.killed: dict = {}
        self.errors: list = []

    def _read_events(self) -> None:
        try:
            with open(os.path.join(self.rundir, "guard.jsonl"), encoding="utf-8") as fh:
                fh.seek(self.offset)
                chunk = fh.read()
        except OSError:
            return
        complete = chunk[:chunk.rfind("\n") + 1]     # never consume a half-written line
        self.offset += len(complete.encode("utf-8"))
        for line in complete.splitlines():
            try:
                e = json.loads(line)
            except ValueError:
                continue
            ev = e.get("event")
            if ev == "gate":
                self.gate_green = e.get("passed") is True
            elif ev == "pre" and e.get("tool") == "run_command" and e.get("decision") == "allow":
                self.saw_command = True
            done = ((ev == "stop" and e.get("decision") == "stop")
                    or (ev == "pre" and e.get("tool") in FINISH_TOOLS and e.get("decision") == "allow"))
            if done and self.gate_green and self.finished_at is None:
                self.finished_at = time.time()

    def candidates(self, agy_pid: int, tree: dict, info: dict) -> dict:
        """pid -> cmdline of the processes that may be killed now. `tree` is
        descendants(agy_pid); `info` is pid -> (cmdline, marked, gate)."""
        shielded = set()
        for pid in tree:
            cmd, _marked, gate = info.get(pid, ("", False, False))
            if pid in self.baseline or self.hook_tag in cmd or gate or MCP_CMDLINE.search(cmd):
                shielded.add(pid)

        def under_shield(pid):
            while pid in tree:
                if pid in shielded:
                    return True
                pid = tree[pid]
            return False

        me = os.getpid()
        return {pid: info[pid][0][:200] for pid in tree
                if pid not in (agy_pid, me) and pid in info and info[pid][1] and not under_shield(pid)}

    def poll(self, agy_pid: int) -> None:
        try:
            tree = descendants(agy_pid, ppid_map())     # scan BEFORE reading events: see baseline
            info = {}
            for pid in tree:
                try:
                    marked, gate = proc_env_has(pid, self.marker, b"CREW_GATE=1")
                    info[pid] = (proc_cmdline(pid, 0), marked, gate)
                except OSError:
                    continue
            new = [p for p in info if p not in self.seen]
            if new:
                self.seen.update(new)
                for p in new:
                    append_jsonl(os.path.join(self.rundir, "procs.jsonl"),
                                 {"t": round(time.time(), 1), "pid": p, "ppid": tree.get(p),
                                  "cmd": info[p][0][:200], "marked": info[p][1]})
            self._read_events()
            if not self.saw_command:
                # The hook logs an allowed run_command before agy spawns it, so
                # a scan taken before that log line cannot contain the command.
                self.baseline.update(tree)
            if self.finished_at is None or time.time() - self.finished_at < self.grace:
                return
            hits = self.candidates(agy_pid, tree, info)
            if hits:
                self.killed.update(hits)
                append_jsonl(os.path.join(self.rundir, "guard.jsonl"),
                             {"event": "background_killed", "procs": {str(k): v for k, v in hits.items()}})
                kill_pids(list(hits))
        except Exception as exc:  # noqa: BLE001 — the watcher must never break the run
            if len(self.errors) < 5:
                self.errors.append(repr(exc)[:300])


def refuse_existing_hooks(repo: str) -> None:
    path = os.path.join(repo, HOOK_FILE)
    if not os.path.lexists(path):
        return
    spec = read_json(path)
    if isinstance(spec, dict) and list(spec) in (["crew"], ["agy-worker"]):    # agy-worker: pre-0.4.0
        raise Refusal(f"{path} e sobra de um run do crew que morreu sem limpar (SIGKILL?), ou "
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
    spec = {"crew": {
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
            grace: int = 180, watch=None):
    """Run the worker CLI with cwd = repo and stdin closed (opencode hangs on an
    open stdin pipe). Output goes to <name>.stdout/.stderr in the run dir.
    `watch(pid)`, if given, is called about once a second while it runs."""
    out_p, err_p = os.path.join(rundir, f"{name}.stdout"), os.path.join(rundir, f"{name}.stderr")
    with open(out_p, "w") as fo, open(err_p, "w") as fe:
        proc = subprocess.Popen(cmd, cwd=repo, stdout=fo, stderr=fe, stdin=subprocess.DEVNULL,
                                start_new_session=True, env=env)
        try:
            deadline = time.time() + timeout_s + grace
            while True:
                try:
                    rc = proc.wait(timeout=max(0.1, min(1.0, deadline - time.time())) if watch
                                   else max(0.1, deadline - time.time()))
                    break
                except subprocess.TimeoutExpired:
                    if time.time() >= deadline:
                        raise
                    if watch:
                        watch(proc.pid)
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

# No policy in here: every tool call is forwarded to `crew.py hook
# oc-pre`, and anything but an explicit allow (a crash, no answer) denies.
# A throw in tool.execute.before blocks the call and the model sees the text
# (lab E4, opencode 1.19.0).
OC_GUARD_JS = """// crew guard for opencode, generated for one run; loaded only through
// OPENCODE_CONFIG_CONTENT of that run. The policy is crew.py's.
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
    env = {**os.environ, **WORKER_ENV, "OPENCODE_DISABLE_AUTOUPDATE": "1", "OPENCODE_DISABLE_SHARE": "1",
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
    with tempfile.TemporaryDirectory(prefix="crew-oc-") as cwd:
        run = lambda *a: subprocess.run([oc, *a], capture_output=True, text=True, timeout=120,  # noqa: E731
                                        cwd=cwd, stdin=subprocess.DEVNULL)
        lines = run("--version").stdout.strip().splitlines()
        proc = run("models", "--standalone")
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
    env[RUN_ENV] = ctx.get("run_id", "")
    deadline = time.time() + task["timeout"]
    fails, warns, runs, restored = [], [], [], set()
    sid, report, msg, n = None, None, prompt, task["max_gate_attempts"]
    try:
        for i in range(1, n + 1):
            left = int(deadline - time.time())
            if left < 30:
                fails.append("timeout da task esgotado antes de o gate e o relatorio ficarem prontos")
                break
            cmd = [oc, "run", *OC_RUN_FLAGS, "--format", "json", "-m", task["model"],
                   *(["-s", sid] if sid else []), oc_message(msg)]
            eprint(f"crew: opencode run {i}/{n} ({task['model']}{', sessao ' + sid if sid else ''})…")
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
# GitHub Copilot CLI backend: repo hooks for one run, gate on agentStop
# --------------------------------------------------------------------------

def cp_hook_rel(run_id: str) -> str:
    return f"{COPILOT_HOOK_DIR}/{COPILOT_HOOK_PREFIX}{run_id}.json"


def refuse_cp_leftovers(repo: str) -> list:
    """Refuses on a hooks file left by a dead run (COPILOT_ALLOW_ALL=true
    would load it, pointing at a dead run dir); returns the repo's own hook
    files, which load too and run with the same trust."""
    d = os.path.join(repo, COPILOT_HOOK_DIR)
    names = sorted(os.listdir(d)) if os.path.isdir(d) else []
    ours = [n for n in names if n.startswith((COPILOT_HOOK_PREFIX, "agy-worker-")) and n.endswith(".json")]
    if ours:
        paths = " ".join(shlex.quote(os.path.join(d, n)) for n in ours)
        raise Refusal(f"sobra de um run do crew em {COPILOT_HOOK_DIR}/ ({', '.join(ours)}), de um run "
                      "que morreu sem limpar ou ainda em curso neste repo. Se nenhum `copilot` estiver "
                      f"rodando aqui, remova so esses arquivos: rm {paths}")
    return [f"{COPILOT_HOOK_DIR}/{n}" for n in names if n.endswith(".json")]


def install_cp_hooks(repo: str, rundir: str, ctx: dict) -> tuple:
    """Write .github/hooks/crew-<run>.json. Returns (relative path,
    directories created by us, deepest first), for remove_cp_hooks."""
    rel = cp_hook_rel(ctx["run_id"])
    path = os.path.join(repo, rel)
    if os.path.lexists(path):
        raise Refusal(f"{rel} ja existe; este script nao sobrescreve arquivo de hooks")
    created, d = [], os.path.dirname(path)
    while not os.path.isdir(d):
        created.append(d)
        d = os.path.dirname(d)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    base = f"{shlex.quote(sys.executable)} {shlex.quote(os.path.abspath(__file__))} hook"
    st = shlex.quote(rundir)
    gate_secs = ctx.get("gate_timeout", DEFAULT_GATE_TIMEOUT) * max(
        1, len(ctx["gate"]["format"]) + len(ctx["gate"]["checks"])) + 60
    # Hook timeouts fail OPEN in Copilot: preToolUse gets a generous 30 s for
    # a handler that answers in well under one, and agentStop the whole gate.
    spec = {"version": 1, "hooks": {
        "sessionStart": [{"type": "command", "bash": f"{base} start --state {st}", "cwd": ".",
                          "timeoutSec": 10}],
        "preToolUse": [{"type": "command", "bash": f"{base} cp-pre --state {st}", "cwd": ".",
                        "timeoutSec": 30}],
        "agentStop": [{"type": "command", "bash": f"{base} cp-stop --state {st}", "cwd": ".",
                       "timeoutSec": gate_secs}],
    }}
    with open(path, "x", encoding="utf-8") as fh:
        json.dump(spec, fh, indent=2)
    write_json(os.path.join(rundir, "hooks.installed.json"), spec)
    return rel, created


def remove_cp_hooks(repo: str, rel: str, created) -> None:
    try:
        os.remove(os.path.join(repo, rel))
    except FileNotFoundError:
        pass
    for d in created:                       # deepest first; only if empty, never rm -r
        try:
            os.rmdir(d)
        except OSError:
            break


def file_sha(path: str):
    try:
        with open(path, "rb") as fh:
            return hashlib.sha256(fh.read()).hexdigest()
    except OSError:
        return None


def preflight_copilot() -> tuple:
    """(binary, warnings). No model listing exists to check against without a
    model call, so the model rule lives in copilot_model_problem."""
    cp = shutil.which("copilot")
    if not cp:
        raise Refusal("copilot nao esta no PATH")
    with tempfile.TemporaryDirectory(prefix="crew-cp-") as cwd:
        proc = subprocess.run([cp, "--version"], capture_output=True, text=True, timeout=60, cwd=cwd,
                              stdin=subprocess.DEVNULL)
    m = re.search(r"(\d+\.\d+\.\d+)", proc.stdout)
    version = m.group(1) if m else "?"
    warns = []
    if version != TESTED_COPILOT_VERSION:
        warns.append(f"copilot {version}; este script so foi exercitado no {TESTED_COPILOT_VERSION}. Carga "
                     "dos hooks, nomes das ferramentas e formato dos eventos podem ter mudado")
    return cp, warns


def copilot_cmd(cp: str, prompt: str, model: str, rundir: str, excluded, max_credits) -> list:
    return [cp, "-p", oc_message(prompt), "--model", model, "--output-format", "json",
            "--allow-all-tools", "--excluded-tools", *excluded, "--disallow-temp-dir", "--no-ask-user",
            "--no-auto-update", "--disable-builtin-mcps", "--max-ai-credits", str(max_credits),
            "--usage-output-file", os.path.join(rundir, "usage.json"),
            "--log-dir", os.path.join(rundir, "copilot-logs")]


def copilot_env(run_id: str) -> dict:
    """COPILOT_ALLOW_ALL must be exactly "true": that is what trusts the cwd
    and loads its hooks (lab: --allow-all-tools and trustedFolders do not).
    It also loads the repo's own skills, plugins and MCP servers. COPILOT_HOME
    stays the user's: isolating it lost the login in the lab."""
    return {**os.environ, **WORKER_ENV, "COPILOT_ALLOW_ALL": "true", "COPILOT_AUTO_UPDATE": "false",
            "NO_COLOR": "1", RUN_ENV: run_id}


def evaluate_cp(rc, stdout: str, stderr: str):
    """(failures, info) for one `copilot -p --output-format json`. Exit 0 came
    with failed work in the lab, so success is read from the events: a
    `result` with exitCode 0, no shell or subagent call, no error event."""
    fails, events = [], []
    if rc == "wrapper-timeout":
        fails.append("timeout: copilot nao terminou e foi encerrado")
    elif rc != 0:
        fails.append(f"copilot saiu com rc={rc}: {tail(stderr.strip(), 400)}")
    for line in stdout.splitlines():
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        if isinstance(ev, dict):
            events.append(ev)
    if not events:
        fails.append("nenhum evento JSON no stdout")
    results = [ev for ev in events if ev.get("type") == "result"]
    if events and not results:
        fails.append("nenhum evento result: o run foi cortado")
    elif results and results[-1].get("exitCode") != 0:
        fails.append(f"evento result com exitCode={results[-1].get('exitCode')!r}")
    tools, failed = {}, 0
    for ev in events:
        data = ev.get("data") or {}
        if ev.get("type") == "tool.execution_start":
            name = str(data.get("toolName", ""))
            tools[name] = tools.get(name, 0) + 1
        elif ev.get("type") == "tool.execution_complete" and data.get("success") is False:
            failed += 1
        elif str(ev.get("type", "")).endswith("error"):
            fails.append(f"evento {ev.get('type')}: {json.dumps(data)[:300]}")
    shell = sorted(t for t in tools if t in COPILOT_SHELL_TOOLS)
    if shell:
        fails.append(f"chamada de shell observada ({shell}), apesar de --excluded-tools: o worker nao devia "
                     "ter shell")
    if "task" in tools:
        fails.append(f"subagente observado ({tools['task']} chamadas de task), apesar de --excluded-tools")
    usage = (results[-1].get("usage") if results else None) or {}
    info = {"session": next((ev.get("sessionId") for ev in results if ev.get("sessionId")), None),
            "text": cp_final_text(stdout) or "", "tools": tools, "tool_failures": failed,
            "premium_requests": usage.get("premiumRequests")}
    return fails, info


def read_cp_usage(path: str):
    """Credits and served model from --usage-output-file, or None. 1 AI credit
    = 1e9 nanoAIU is inferred from the CLI footer, not documented."""
    u = read_json(path)
    if not isinstance(u, dict):
        return None
    nano = u.get("totalNanoAiu")
    return {"ai_credits": round(nano / 1e9, 4) if isinstance(nano, (int, float)) else None,
            "premium_requests": u.get("totalPremiumRequestCost"),
            "served_models": sorted((u.get("modelMetrics") or {}).keys()),
            "current_model": u.get("currentModel"), "ai_credits_status": u.get("aiCreditsStatus"),
            "api_duration_ms": u.get("totalApiDurationMs")}


def run_copilot(cp: str, prompt: str, model: str, repo: str, rundir: str, ctx: dict, timeout_s: int,
                excluded, max_credits):
    """Install the run's hooks, run copilot, always remove them. Returns
    (rc, stdout, stderr, failures about the hooks file)."""
    rel, created = install_cp_hooks(repo, rundir, ctx)
    sha = file_sha(os.path.join(repo, rel))
    fails = []
    try:
        rc, stdout, stderr = run_agy(copilot_cmd(cp, prompt, model, rundir, excluded, max_credits), repo,
                                     rundir, timeout_s, name="copilot", env=copilot_env(ctx["run_id"]),
                                     grace=30)
    finally:
        if file_sha(os.path.join(repo, rel)) != sha:
            fails.append(f"o arquivo de hooks do run ({rel}) mudou durante o run: o guard pode ter sido trocado")
        remove_cp_hooks(repo, rel, created)
    return rc, stdout, stderr, fails


# --------------------------------------------------------------------------
# subcommands
# --------------------------------------------------------------------------

def base_ctx(repo, task, mode):
    return {
        "mode": mode, "repo": repo, "scope": task["scope"], "side_effects": task["side_effects"],
        "allow_paths": task["allow_paths"], "gate": task["gate"],
        "secret_globs": task.get("secret_globs", DEFAULT_SECRET_GLOBS),
        "gate_timeout": task["gate_timeout"], "max_gate_attempts": task["max_gate_attempts"],
        "gate_commands": task["gate"]["format"] + task["gate"]["checks"],
        "deny_patterns": DENY_COMMANDS + (OPENCODE_DENY_COMMANDS if task.get("backend") == "opencode" else [])
        + [(p, "regra do projeto") for p in task["deny_commands"]],
    }


def cmd_delegate(a) -> int:
    trap_signals()
    task = load_task(a.task, backend=a.backend, model=a.model)
    opencode = task["backend"] == "opencode"
    copilot = task["backend"] == "copilot"
    repo = repo_root(a.repo or os.getcwd())
    git(repo, "rev-parse", "--verify", "HEAD")
    other_cp_hooks = refuse_cp_leftovers(repo) if copilot else []
    dirty = changed_paths(repo)
    if dirty:
        raise Refusal("arvore suja; commite ou guarde antes (o diff do worker tem que ser so dele): "
                      + ", ".join(dirty[:10]))
    if task["backend"] == "agy":
        refuse_existing_hooks(repo)
    rundir = new_rundir(repo, "delegate")
    eprint(f"crew: run dir {rundir}")
    if opencode:
        saved = snapshot_files(repo, OPENCODE_CONFIG_FILES)    # before any opencode process
        try:
            oc, pre_warns = preflight_opencode(task["model"])
        finally:
            if restore_files(repo, saved):
                eprint("crew: o preflight do opencode reescreveu opencode.json; restaurado")
    elif copilot:
        cp, pre_warns = preflight_copilot()
        if other_cp_hooks:
            pre_warns.append(f"hooks do proprio repo em {COPILOT_HOOK_DIR}/ carregam junto com os do run, com "
                             f"a mesma confianca (COPILOT_ALLOW_ALL=true): {other_cp_hooks}")
    else:
        pre_warns = preflight_agy(task["model"], task["min_quota"], not a.no_quota_probe, rundir)
    ctx = base_ctx(repo, task, "delegate")
    ctx["run_id"] = os.path.basename(rundir)
    if copilot:
        ctx.update(ignore_paths=[cp_hook_rel(ctx["run_id"])], report_schema=task["report_schema"],
                   events_file=os.path.join(rundir, "copilot.stdout"))
    write_json(os.path.join(rundir, "ctx.json"), ctx)
    write_json(os.path.join(rundir, "task.json"), task)
    schema_path = os.path.join(rundir, "report.schema.json")
    write_json(schema_path, task["report_schema"])
    prompt = compose_prompt(task, repo)
    with open(os.path.join(rundir, "prompt.md"), "w", encoding="utf-8") as fh:
        fh.write(prompt)
    head = git(repo, "rev-parse", "HEAD").strip()
    integ_before, ignored_before = integrity_state(repo, rundir), ignored_state(repo)
    started = time.time()
    if opencode:
        fails, warns, report, run_info = drive_opencode(oc, task, repo, rundir, prompt, ctx, saved)
        run_info["wall_seconds"] = round(time.time() - started)
    elif copilot:
        eprint(f"crew: copilot rodando ({task['model']}, timeout {task['timeout']}s)…")
        rc, stdout, stderr, fails = run_copilot(cp, prompt, task["model"], repo, rundir, ctx, task["timeout"],
                                                COPILOT_EXCLUDED_TOOLS, task["max_ai_credits"])
        run_fails, info = evaluate_cp(rc, stdout, stderr)
        fails += run_fails
        report = extract_report(info.pop("text"))
        fails += report_problems(report, task["report_schema"])
        if isinstance(report, dict) and report.get("status") in ("partial", "blocked"):
            fails.append(f"o worker se declarou {report['status']!r}")
        warns = []
        usage = read_cp_usage(os.path.join(rundir, "usage.json"))
        if usage is None:
            warns.append("usage.json do copilot ausente ou ilegivel: creditos gastos desconhecidos")
        run_info = {"rc": rc, "wall_seconds": round(time.time() - started), **info, "usage": usage}
    else:
        cmd = ["agy", "-p", prompt, "--model", task["model"], "--output-format", "json",
               "--json-schema", schema_path, "--print-timeout", f"{task['timeout']}s",
               "--dangerously-skip-permissions"]
        created = install_hooks(repo, rundir, ctx)
        watcher = BackgroundWatcher(rundir, ctx["run_id"])
        try:
            eprint(f"crew: agy rodando ({task['model']}, timeout {task['timeout']}s)…")
            rc, stdout, stderr = run_agy(cmd, repo, rundir, task["timeout"],
                                         env={**os.environ, **WORKER_ENV, RUN_ENV: ctx["run_id"]},
                                         watch=watcher.poll)
        finally:
            remove_hooks(repo, created)
        fails, warns, env = evaluate_run(rc, stdout, stderr, "delegate", task["report_schema"])
        report = env.get("structured_output") if isinstance(env, dict) else None
        run_info = {"rc": rc, "wall_seconds": round(time.time() - started), **(
            {k: env.get(k) for k in ("status", "duration_seconds", "num_turns", "usage", "conversation_id")}
            if isinstance(env, dict) else {})}
        run_info["background_killed"] = {str(p): c for p, c in watcher.killed.items()}
        if watcher.killed:
            warns.append(f"{len(watcher.killed)} processo(s) em segundo plano do worker encerrado(s) "
                         f"{BG_GRACE_S} s depois de ele terminar com gate verde, para o agy poder sair: "
                         + "; ".join(f"{p} {c}" for p, c in watcher.killed.items()))
        if watcher.errors:
            warns.append(f"o vigia de processos em segundo plano falhou: {watcher.errors}")
    warns = pre_warns + warns
    tampered = diff_state(integ_before, integrity_state(repo, rundir))
    ignore = ctx.get("ignore_paths", [])
    if tampered:
        fails.append("config, hooks ou flags de indice do git, ou o ctx.json do run, mudaram durante o "
                     f"run; o veredito abaixo nao e confiavel: {tampered}")
    events = guard_events(rundir)
    if copilot:
        # Any of our hooks answering proves the file loaded; sessionStart alone
        # was never observed firing in the lab.
        if not any(e.get("event") in ("session_start", "pre", "stop") for e in events):
            fails.append("os hooks do crew nao carregaram no copilot (nenhum evento de hook "
                         "registrado): o run nao teve guard rails; trate o diff como nao confiavel")
    elif not any(e.get("event") == "session_start" for e in events):
        fails.append(("o plugin de guard do opencode nao carregou" if opencode else
                      "os hooks do crew nao carregaram") + " (nenhum SessionStart registrado): "
                     "o run nao teve guard rails; trate o diff como nao confiavel")
    if git(repo, "rev-parse", "HEAD").strip() != head:
        fails.append("HEAD mudou durante o run (commit ou checkout passou pelo guard)")
    # The gate verdict that counts is the one for the tree as it is now.
    st = read_json(os.path.join(rundir, "gate-state.json"), {"attempts": 0})
    fp = fingerprint(repo, task["side_effects"], ignore)
    if st.get("fingerprint") == fp and st.get("passed") is True:
        passed, text, source = True, st["text"], "cached (estado identico ao ultimo gate verde do hook)"
    else:
        passed, text, _ = run_gate(repo, ctx)
        with open(os.path.join(rundir, "gate-final.log"), "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
        source = f"final (rodado apos o {task['backend']})"
    if not passed:
        fails.append("gate falhou no estado final da arvore")
    cls = classify(changed_paths(repo, ignore), task["scope"], task["side_effects"])
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
    stopped = stop_run_procs(ctx["run_id"])
    if stopped:
        warns.append("processos deixados pelo run encerrados (traziam a marca do run): "
                     + "; ".join(f"{p} {c}" for p, c in stopped.items()))
    # By marker, not by cwd: a cwd scan also listed the orchestrating Claude
    # session's own `sleep 2` wait loop (false positive, 2026-10-13).
    leftover = marked_procs(ctx["run_id"])
    if leftover:
        warns.append("processos com a marca do run ainda vivos depois de SIGTERM e SIGKILL: "
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
    eprint(f"crew: {'OK' if verdict['ok'] else 'FALHOU'} — {len(fails)} falha(s), "
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
    opencode, copilot = a.backend == "opencode", a.backend == "copilot"
    model = a.model or {"opencode": OPENCODE_DEFAULT_MODEL, "copilot": COPILOT_DEFAULT_MODEL}.get(
        a.backend, DEFAULT_MODEL)
    if copilot:
        problem = copilot_model_problem(model, a.copilot_model_override)
        if problem:
            raise Refusal(problem)
        other_cp_hooks = refuse_cp_leftovers(repo)
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
    eprint(f"crew: run dir {rundir}")
    if opencode:
        saved = snapshot_files(repo, OPENCODE_CONFIG_FILES)    # before any opencode process
        try:
            oc, pre_warns = preflight_opencode(model)
        finally:
            if restore_files(repo, saved):
                eprint("crew: o preflight do opencode reescreveu opencode.json; restaurado")
    elif copilot:
        cp, pre_warns = preflight_copilot()
        if other_cp_hooks:
            pre_warns.append(f"hooks do proprio repo em {COPILOT_HOOK_DIR}/ carregam junto: {other_cp_hooks}")
    else:
        pre_warns = preflight_agy(model, a.min_quota, not a.no_quota_probe, rundir)
    prompt = question
    if diff_txt:
        prompt += f"\n\n## Diff under review (`git diff {a.diff}`)\n```diff\n{diff_txt}\n```"
    prompt += ("\n\n---\nYou are a read-only reviewer. Do not modify files and do not run commands; "
               f"read files under `{repo}` as needed. Every finding must quote the exact code or text "
               "that supports it in `evidence`. Prefer `unsure` over a guess.\n")
    if copilot:
        prompt += "You have no shell and no editing tools; use only the read and search tools.\n"
    prompt += report_rule({"backend": a.backend, "report_schema": schema})
    with open(os.path.join(rundir, "prompt.md"), "w", encoding="utf-8") as fh:
        fh.write(prompt)
    # opencode has no plan mode: scope [] denies every write, and every shell
    # command is denied, both by the guard plugin.
    ctx = {"mode": "review", "repo": repo, "scope": [], "side_effects": [], "allow_paths": [],
           "secret_globs": DEFAULT_SECRET_GLOBS,
           "gate": {"format": [], "checks": [], "forbid": []}, "gate_timeout": 60,
           "max_gate_attempts": 0, "gate_commands": [],
           "deny_patterns": REVIEW_DENY_ALL if opencode or copilot else DENY_COMMANDS,
           "run_id": os.path.basename(rundir)}
    if copilot:
        ctx["ignore_paths"] = [cp_hook_rel(ctx["run_id"])]
    write_json(os.path.join(rundir, "ctx.json"), ctx)
    schema_path = os.path.join(rundir, "review.schema.json")
    write_json(schema_path, schema)
    fp_before, ignored_before = fingerprint(repo, []), ignored_state(repo)
    integ_before = integrity_state(repo, rundir)
    if opencode:
        env_oc = opencode_env(write_oc_guard(rundir), False)
        try:
            eprint(f"crew: review rodando (opencode, {model})…")
            rc, stdout, stderr = run_agy([oc, "run", *OC_RUN_FLAGS, "--format", "json", "-m", model,
                                          oc_message(prompt)], repo, rundir, timeout_s,
                                         name="opencode-1", env=env_oc, grace=0)
        finally:
            restored = restore_files(repo, saved)
        fails, info = evaluate_oc(rc, stdout, stderr)
        report = extract_report(info.pop("text"))
        fails += report_problems(report, schema)
        warns = pre_warns + ([f"o opencode reescreveu {sorted(restored)}; bytes restaurados"] if restored else [])
        run_info = {"rc": rc, **info}
    elif copilot:
        eprint(f"crew: review rodando (copilot, {model}, sem shell nem apply_patch)…")
        rc, stdout, stderr, fails = run_copilot(cp, prompt, model, repo, rundir, ctx, timeout_s,
                                                COPILOT_REVIEW_EXCLUDED_TOOLS, COPILOT_MIN_AI_CREDITS)
        run_fails, info = evaluate_cp(rc, stdout, stderr)
        fails += run_fails
        report = extract_report(info.pop("text"))
        fails += report_problems(report, schema)
        usage = read_cp_usage(os.path.join(rundir, "usage.json"))
        warns = pre_warns + ([] if usage else ["usage.json do copilot ausente: creditos gastos desconhecidos"])
        run_info = {"rc": rc, **info, "usage": usage}
    else:
        cmd = ["agy", "-p", prompt, "--model", model, "--mode", "plan", "--output-format", "json",
               "--json-schema", schema_path, "--print-timeout", f"{timeout_s}s"]
        created = install_hooks(repo, rundir, ctx)
        try:
            eprint(f"crew: review rodando ({model}, --mode plan)…")
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
    if copilot:
        if not any(e.get("event") in ("session_start", "pre", "stop") for e in guard_events(rundir)):
            fails.append("os hooks do crew nao carregaram no copilot (nenhum evento de hook): o "
                         "review rodou sem nada que negasse escrita")
    elif not any(e.get("event") == "session_start" for e in guard_events(rundir)):
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

    tmp = tempfile.mkdtemp(prefix="crew-selftest-")
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
        example = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "shared",
                               "task.example.json")
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
        check(pre("read_file", Path=f"{repo}/src/a.txt")["decision"] == "allow", "agy 1.4.4 read_file in repo")
        check(pre("read_file", Path="/etc/passwd")["decision"] == "deny", "agy 1.4.4 read_file outside")
        check(pre("read_file", Path=f"{repo}/.env")["decision"] == "deny", "agy 1.4.4 read_file secret")
        check(pre("write_file", Path=f"{repo}/side.json", Overwrite=True)["decision"] == "deny",
              "agy 1.4.4 write_file out of scope")
        check(pre("edit_file", Path="src/../.git/config", Target="a", Replacement="b")["decision"] == "deny",
              "agy 1.4.4 edit_file into .git")
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
        # secrets: by tool and by shell, .env.example still readable, [] turns it off
        check(pre("view_file", AbsolutePath=f"{repo}/.env")["decision"] == "deny", "segredo: view .env")
        check(pre("view_file", AbsolutePath=f"{repo}/apps/web/.dev.vars")["decision"] == "deny",
              "segredo: .dev.vars")
        check(pre("view_file", AbsolutePath=f"{repo}/.env.example")["decision"] == "allow",
              "segredo: .env.example liberado")
        check(pre("run_command", CommandLine="cat .env")["decision"] == "deny", "segredo: cat .env")
        check(pre("run_command", CommandLine="grep DATABASE apps/api/.env.production")["decision"]
              == "deny", "segredo: grep em .env.production")
        check(pre("run_command", CommandLine="cat certs/server.pem")["decision"] == "deny", "segredo: pem")
        check(pre("run_command", CommandLine="node scripts/env-check.js")["decision"] == "allow",
              "segredo: nome parecido nao e segredo")
        nosec = dict(ctx, secret_globs=[])
        check(decide_pre({"toolCall": {"name": "view_file", "args": {"AbsolutePath": f"{repo}/.env"}}},
                         nosec)["decision"] == "allow", "segredo: lista vazia desliga")
        # WaitMsBeforeAsync is no longer overwritten: it did not keep the command in the foreground
        check(pre("run_command", CommandLine="npm test") == {"decision": "allow"}, "run_command sem overwrite")
        check("overwrite" not in pre("view_file", AbsolutePath=f"{repo}/src/a.txt"), "sem overwrite fora do shell")
        check(pre("write_to_file", TargetFile=f"{repo}/src/b.txt", CodeContent="/etc/x")["decision"]
              == "allow", "escrita no escopo; conteudo nao e escaneado")
        check(pre("write_to_file", TargetFile=f"{repo}/side.json")["decision"] == "deny", "fora do escopo")
        check(pre("write_file", Path=f"{repo}/src/b.txt", Content="/etc/x", Overwrite=True)["decision"]
              == "allow", "agy 1.4.4 write_file in scope, path-like content ignored")
        check(pre("edit_file", Path=f"{repo}/src/b.txt", Target="/etc/a", Replacement="/etc/b")["decision"]
              == "allow", "agy 1.4.4 edit_file in scope")
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
                  "echo '{}' > \"$(git rev-parse --git-path crew)/runs/r/ctx.json\"",
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

        # copilot backend: model rule, task fields, tool translation to the same decide_pre
        ctask = normalize_task({"prompt": "x", "scope": ["src/*"], "backend": "copilot",
                                "gate": {"checks": ["true"]}})
        check(ctask["model"] == "auto" and ctask["max_ai_credits"] == COPILOT_MIN_AI_CREDITS,
              "copilot: modelo auto e backstop de 30 creditos")
        for bad, why in ((dict(model="gpt-5.6-luna"), "modelo fixo sem override"),
                         (dict(model="claude-sonnet-5.5", copilot_model_override="yes"), "override nao booleano"),
                         (dict(max_ai_credits=10), "max_ai_credits abaixo de 30"),
                         (dict(max_gate_attempts=9), "mais tentativas que o limite de bloqueios"),
                         (dict(scope=["*"]), "scope cobre .github/hooks"),
                         (dict(scope=[".claude/*"]), "scope cobre .claude/settings.json")):
            try:
                normalize_task({"prompt": "x", "scope": ["src/*"], "backend": "copilot",
                                "gate": {"checks": ["true"]}, **bad})
                check(False, f"task copilot invalida aceita: {why}")
            except Refusal as exc:
                check(why != "modelo fixo sem override" or "Free" in str(exc), f"{why}: {exc}")
        check(normalize_task({"prompt": "x", "scope": ["src/*"], "backend": "copilot", "gate": {"checks": ["t"]},
                              "model": "claude-sonnet-5.5", "copilot_model_override": True})["model"]
              == "claude-sonnet-5.5", "override libera outro modelo")
        check(copilot_model_problem("auto", False) is None and copilot_model_problem("x", False),
              "regra do modelo")
        cprompt = compose_prompt(ctask, repo)
        check("NO shell" in cprompt and "Run the format and check commands yourself" not in cprompt
              and "ONE JSON object" in cprompt and "after gate feedback" in cprompt,
              "prompt do copilot: sem shell, gate automatico, relatorio em toda mensagem final")
        check("Run the format and check commands yourself" in compose_prompt(task, repo), "prompt do agy intacto")
        cctx = base_ctx(repo, ctask, "delegate")
        cp = lambda tool, args: decide_cp({"toolName": tool, "toolArgs": args}, cctx)["decision"]  # noqa: E731
        for tool, args, want, why in (
                ("view", {"path": f"{repo}/src/a.txt"}, "allow", "view no repo"),
                ("view", {"path": "src/a.txt", "view_range": [1, 5]}, "allow", "view relativo"),
                ("view", {"path": "/etc/passwd"}, "deny", "view fora do repo"),
                ("view", {"path": f"{repo}/.env"}, "deny", "view de segredo"),
                ("view", json.dumps({"path": "/etc/passwd"}), "deny", "args como string JSON"),
                ("glob", {"pattern": "src/**/*.ts"}, "allow", "glob no repo"),
                ("glob", {"pattern": "/etc/*"}, "deny", "glob absoluto"),
                ("grep", {"pattern": "/api/v1", "path": "src", "glob": "*.ts"}, "allow", "regex nao e caminho"),
                ("grep", {"pattern": "x", "path": "../.."}, "deny", "grep fora"),
                ("apply_patch", "*** Begin Patch\n*** Add File: src/b.txt\n+x\n*** End Patch\n", "allow",
                 "patch no escopo (string crua, como no lab)"),
                ("apply_patch", "*** Begin Patch\n*** Add File: NOTES.txt\n+x\n*** End Patch\n", "deny",
                 "patch fora do escopo"),
                ("apply_patch", "*** Add File: ../NOTES.txt\n+x\n", "deny", "patch com .."),
                ("apply_patch", "*** Add File: src/../NOTES.txt\n+x\n", "deny", "patch src/.."),
                ("apply_patch", "*** Update File: src/a.txt\n*** Move to: /tmp/x\n", "deny", "patch move para fora"),
                ("apply_patch", "*** Add File: src/a.txt\n+x\n*** Add File: side.json\n+y\n", "deny",
                 "patch com um alvo fora"),
                ("apply_patch", "garbage", "deny", "patch sem alvo"),
                ("apply_patch", "*** Add File: .github/hooks/crew-x.json\n+{}\n", "deny",
                 "patch no arquivo de hooks"),
                ("create", {"path": "src/c.txt", "file_text": "see /etc/passwd"}, "allow", "create no escopo"),
                ("create", {"path": "top.txt", "file_text": "x"}, "deny", "create fora do escopo"),
                ("edit", {"path": "src/a.txt", "old_str": "/a/", "new_str": "/b/"}, "allow", "edit no escopo"),
                ("edit", {"path": "side.json", "old_str": "a", "new_str": "b"}, "deny", "edit fora"),
                ("bash", {"command": "ls"}, "deny", "bash sempre negado"),
                ("read_bash", {"shellId": "1"}, "deny", "read_bash negado"),
                ("task", {"prompt": "x"}, "deny", "subagente"),
                ("web_fetch", {"url": "https://example.com"}, "deny", "rede"),
                ("github-mcp-server-list_issues", {"owner": "x"}, "deny", "MCP do GitHub"),
                ("skill", {"skill": "x"}, "deny", "skill"),
                ("report_intent", {"intent": "Editing /etc"}, "allow", "report_intent inerte"),
                ("brand_new_tool", {}, "deny", "ferramenta desconhecida")):
            check(cp(tool, args) == want, f"copilot {why}: {tool} {args}")
        crctx = dict(cctx, scope=[], deny_patterns=REVIEW_DENY_ALL, mode="review")
        check(decide_cp({"toolName": "create", "toolArgs": {"path": "src/a.txt"}}, crctx)["decision"] == "deny",
              "review copilot nega escrita")
        check(decide_cp({"toolName": "view", "toolArgs": {"path": "src/a.txt"}}, crctx)["decision"] == "allow",
              "review copilot le")
        check(cp_hook_output("cp-pre", {"decision": "allow"}) == "", "allow do copilot nao imprime nada")
        dj = json.loads(cp_hook_output("cp-pre", {"decision": "deny", "reason": "r"}))
        check(dj == {"permissionDecision": "deny", "permissionDecisionReason": "r"}, "deny no formato do copilot")
        check(json.loads(cp_hook_output("cp-stop", {"decision": "stop"})) == {"decision": "allow"},
              "stop vira allow no copilot")

        # copilot events: exit 0 with failed work, shell, subagent, missing result
        def cpev(*evs):
            return "\n".join(json.dumps(e) for e in evs)
        tstart = lambda n: {"type": "tool.execution_start", "data": {"toolName": n, "arguments": "{}"}}  # noqa: E731
        msg = lambda c: {"type": "assistant.message", "data": {"content": c, "phase": "final_answer"}}  # noqa: E731
        res = lambda c=0: {"type": "result", "sessionId": "s1", "exitCode": c, "usage": {"premiumRequests": 2}}  # noqa: E731
        f, info = evaluate_cp(0, cpev(tstart("view"), {"type": "tool.execution_complete", "data": {
            "success": False}}, msg('ok {"status": "done"}'), msg(""), res()), "")
        check(f == [] and info["session"] == "s1" and info["tools"] == {"view": 1} and info["tool_failures"] == 1
              and info["premium_requests"] == 2 and extract_report(info["text"]) == {"status": "done"},
              f"stream bom do copilot: {f} {info}")
        f, _ = evaluate_cp(0, cpev(tstart("bash"), res()), "")
        check(any("shell" in x for x in f), "chamada de bash reprova")
        f, _ = evaluate_cp(0, cpev(tstart("task"), res()), "")
        check(any("subagente" in x for x in f), "chamada de task reprova")
        f, _ = evaluate_cp(0, cpev(msg("x")), "")
        check(any("result" in x for x in f), "sem result reprova")
        f, _ = evaluate_cp(0, cpev(res(1)), "")
        check(any("exitCode" in x for x in f), "result com exitCode != 0 reprova")
        f, _ = evaluate_cp(1, cpev(res()), "boom")
        check(any("rc=1" in x for x in f), "rc != 0 reprova")
        f, _ = evaluate_cp(0, "", "")
        check(any("nenhum evento" in x for x in f), "stdout vazio reprova")
        f, _ = evaluate_cp(0, cpev({"type": "session.error", "data": {"message": "quota"}}, res()), "")
        check(any("session.error" in x for x in f), "evento de erro reprova")
        upath = os.path.join(tmp, "usage.json")
        write_json(upath, {"totalPremiumRequestCost": 2, "totalNanoAiu": 939943800, "aiCreditsStatus": "complete",
                           "modelMetrics": {"gpt-5.6-luna": {}}, "currentModel": "gpt-5.6-luna"})
        u = read_cp_usage(upath)
        check(u["ai_credits"] == 0.9399 and u["served_models"] == ["gpt-5.6-luna"] and u["premium_requests"] == 2,
              f"usage do copilot: {u}")
        check(read_cp_usage(os.path.join(tmp, "nope.json")) is None, "usage ausente")
        cmdl = copilot_cmd("copilot", "-x", "auto", "/r", COPILOT_EXCLUDED_TOOLS, 30)
        i = cmdl.index("--excluded-tools")
        check(cmdl[i + 1:i + 3] == ["bash", "task"] and "--disallow-temp-dir" in cmdl and cmdl[2] == "Task:\n-x"
              and "--allow-all-paths" not in cmdl and "--allow-all" not in cmdl, "linha do copilot")
        check(copilot_env("rid")["COPILOT_ALLOW_ALL"] == "true" and copilot_env("rid")[RUN_ENV] == "rid"
              and copilot_env("rid")["NX_DAEMON"] == "false", "ambiente do copilot")

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
        rid = f"selftest-{os.getpid()}"
        child = subprocess.Popen(["sleep", "60"], env={**os.environ, RUN_ENV: rid},
                                 start_new_session=True)
        other = subprocess.Popen(["sleep", "60"], start_new_session=True)
        time.sleep(0.3)
        hit = stop_run_procs(rid)
        child.wait(timeout=10)
        check(child.pid in hit and child.returncode is not None, "processo marcado encerrado")
        check(other.poll() is None, "processo sem a marca intocado")
        other.kill()
        other.wait()
        check(stop_run_procs("") == {}, "sem run_id nao encerra nada")

        # BackgroundWatcher: who may be killed, from a synthetic tree (agy = 1)
        bw = BackgroundWatcher(tmp, "rid")
        bw.baseline = {12}
        tree = {10: 1, 11: 10, 12: 1, 13: 12, 14: 1, 15: 1, 16: 1, 17: 14}
        info = {10: (f"{bw.hook_tag} stop --state x", True, False), 11: ("npx tsc", True, True),
                12: ("agy-helper", True, False), 13: ("node child-of-baseline", True, False),
                14: ("bash -c nx run web:typecheck", True, False), 15: ("sleep 9", False, False),
                16: ("uv tool uvx --from x kino --mcp", True, False), 17: ("node tsc", True, False)}
        check(set(bw.candidates(1, tree, info)) == {14, 17},
              "vigia: so comando marcado do worker; hook, gate, baseline, MCP e sem marca ficam")
        tree[1] = 0
        info[1] = ("agy -p", True, False)
        check(1 not in bw.candidates(1, tree, info), "vigia: nunca o proprio agy")

        # BackgroundWatcher: done only after a green gate
        def bw_events(*evs):
            d = tempfile.mkdtemp(dir=tmp)
            for e in evs:
                append_jsonl(os.path.join(d, "guard.jsonl"), e)
            w = BackgroundWatcher(d, "rid")
            w._read_events()
            return w
        green, red = {"event": "gate", "passed": True}, {"event": "gate", "passed": False}
        cmd_ev = {"event": "pre", "tool": "run_command", "decision": "allow"}
        check(bw_events(cmd_ev, green, {"event": "stop", "decision": "stop"}).finished_at,
              "vigia: Stop com gate verde = terminou")
        check(bw_events(green, {"event": "pre", "tool": "finish", "decision": "allow"}).finished_at,
              "vigia: finish permitido com gate verde = terminou")
        check(bw_events(red, {"event": "pre", "tool": "finish", "decision": "allow"}).finished_at is None,
              "vigia: finish com gate vermelho nao conta")
        check(bw_events(green, red, {"event": "stop", "decision": "stop"}).finished_at is None,
              "vigia: so o ultimo gate conta")
        check(bw_events(cmd_ev, {"event": "stop", "decision": "continue"}).finished_at is None,
              "vigia: Stop com continue nao conta")

        # BackgroundWatcher against real processes: a fake agy with a helper
        # started before the first command and a worker command after it
        wd = tempfile.mkdtemp(dir=tmp)
        flag = os.path.join(wd, "spawn")
        fake = subprocess.Popen(
            ["bash", "-c", f"sleep 60 & while [ ! -e {shlex.quote(flag)} ]; do sleep 0.05; done; "
                           "sleep 61 & env -u " + RUN_ENV + " sleep 62 & wait"],
            env={**os.environ, RUN_ENV: rid}, start_new_session=True)
        try:
            w = BackgroundWatcher(wd, rid, grace=0.3)
            t0 = time.time()
            while time.time() - t0 < 5 and not any("sleep 60" in proc_cmdline(p)
                                                   for p in descendants(fake.pid, ppid_map())
                                                   if os.path.exists(f"/proc/{p}")):
                time.sleep(0.05)
            w.poll(fake.pid)
            append_jsonl(os.path.join(wd, "guard.jsonl"), cmd_ev)
            open(flag, "w").close()
            kids = {}
            t0 = time.time()
            # wait for the three sleeps by name: the fake agy's own bash is a
            # key too, and `env -u ...` shows its own cmdline until it execs
            while time.time() - t0 < 5 and not {"sleep 60", "sleep 61", "sleep 62"} <= kids.keys():
                time.sleep(0.05)
                kids = {}
                for p in descendants(fake.pid, ppid_map()):
                    try:
                        kids[proc_cmdline(p)] = p
                    except OSError:
                        pass
            w.poll(fake.pid)
            check(w.finished_at is None and not w.killed, "vigia: nada antes de o worker terminar")
            append_jsonl(os.path.join(wd, "guard.jsonl"), green)
            append_jsonl(os.path.join(wd, "guard.jsonl"), {"event": "stop", "decision": "stop"})
            w.poll(fake.pid)
            check(not w.killed, "vigia: espera a carencia")
            time.sleep(0.4)
            w.poll(fake.pid)
            alive = {c: os.path.exists(f"/proc/{p}") for c, p in kids.items()}
            check(set(w.killed.values()) == {"sleep 61"} and not alive.get("sleep 61")
                  and alive.get("sleep 60") and alive.get("sleep 62") and fake.poll() is None,
                  f"vigia: so o comando do worker encerrado; helper, sem marca e o agy vivos ({w.killed}, {alive})")
            check(os.path.isfile(os.path.join(wd, "procs.jsonl")), "vigia: arvore registrada em procs.jsonl")
        finally:
            os.killpg(fake.pid, signal.SIGKILL)     # our own fake agy's group
            fake.wait()
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
        ok, text, _ = run_gate(repo, dict(ctx, gate=dict(ctx["gate"], checks=['test "$CREW_GATE" = 1'])))
        check(ok, "gate exporta CREW_GATE")
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
        check(r["decision"] == "continue" and "finish" in r["reason"],
              f"stop com gate verde e sem finish pede o relatorio: {r}")
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
        with open(os.path.join(repo, "src", "nf.txt"), "w") as fh:
            fh.write("x\n")
        rd_save = rundir
        for name in ("nofinish", "finished"):
            rundir = os.path.join(tmp, name)
            os.makedirs(rundir)
            write_json(os.path.join(rundir, "ctx.json"), dict(
                ctx, max_gate_attempts=9, gate=dict(ctx["gate"], format=[], checks=["true"]), scope=["*"]))
        rundir = os.path.join(tmp, "nofinish")
        got = [hook("stop", {"terminationReason": "NO_TOOL_CALL"})["decision"] for _ in range(AGY_REPORT_ASKS + 1)]
        check(got == ["continue"] * AGY_REPORT_ASKS + ["stop"], f"pede o finish no maximo {AGY_REPORT_ASKS} vezes: {got}")
        rundir = os.path.join(tmp, "finished")
        hook("pre", {"toolCall": {"name": "finish", "args": {}}})
        r = hook("stop", {"terminationReason": "TERMINAL_STEP_TYPE"})
        check(r["decision"] == "stop", f"stop com gate verde depois do finish para: {r}")
        rundir = rd_save
        os.remove(os.path.join(repo, "src", "nf.txt"))
        os.remove(os.path.join(rundir, "ctx.json"))
        check(hook("pre", {"toolCall": {"name": "view_file", "args": {}}})["decision"] == "deny",
              "guard quebrado nega em vez de devolver {}")
        check(hook("stop", {})["decision"] == "stop", "stop quebrado deixa parar")
        check(hook("oc-pre", {"tool": "read", "args": {}})["decision"] == "deny", "oc-pre quebrado nega")
        events = guard_events(rundir)
        check(any(e.get("event") == "session_start" for e in events), "marcador de SessionStart")

        # copilot hooks end to end: cp-pre output contract, gate and report on agentStop
        os.remove(os.path.join(repo, "outside.txt"))
        cprun = os.path.join(tmp, "cprun")
        os.makedirs(cprun)
        once = os.path.join(tmp, "gate-once")
        evfile = os.path.join(cprun, "copilot.stdout")
        write_json(os.path.join(cprun, "ctx.json"), dict(
            ctx, max_gate_attempts=3, run_id="cprun", ignore_paths=[cp_hook_rel("cprun")],
            events_file=evfile, report_schema={"type": "object", "required": ["status"]},
            gate=dict(ctx["gate"], format=[], checks=[f"test -e {shlex.quote(once)} || "
                                                      f"{{ touch {shlex.quote(once)}; false; }}"])))

        def cphook(event, payload):
            p = subprocess.run([sys.executable, os.path.abspath(__file__), "hook", event, "--state", cprun],
                               input=json.dumps(payload), capture_output=True, text=True, timeout=60)
            return p.returncode, p.stdout.strip()
        rc, out = cphook("cp-pre", {"toolName": "view", "toolArgs": {"path": f"{repo}/src/a.txt"}})
        check(rc == 0 and out == "", f"cp-pre allow: saida vazia ({out!r})")
        rc, out = cphook("cp-pre", {"toolName": "apply_patch", "toolArgs": "*** Add File: ../x\n+x\n"})
        check(rc == 0 and json.loads(out)["permissionDecision"] == "deny", "cp-pre deny com motivo")
        with open(evfile, "w") as fh:
            fh.write(json.dumps(msg("done, no report")) + "\n")
        rc, out = cphook("cp-stop", {"stop_hook_active": False})
        check(json.loads(out)["decision"] == "block" and "gate FAILED" in json.loads(out)["reason"],
              f"agentStop com gate vermelho bloqueia: {out}")
        rc, out = cphook("cp-stop", {"stop_hook_active": True})
        check(json.loads(out)["decision"] == "block" and "report" in json.loads(out)["reason"],
              f"gate verde sem relatorio pede o relatorio: {out}")
        with open(evfile, "a") as fh:
            fh.write(json.dumps(msg('ok {"status": "done"}')) + "\n")
        rc, out = cphook("cp-stop", {"stop_hook_active": True})
        check(json.loads(out) == {"decision": "allow"}, f"gate verde com relatorio libera: {out}")
        cst = read_json(os.path.join(cprun, "gate-state.json"))
        check(cst["runs"] == 2 and cst["attempts"] == 3, f"gate do copilot: verde em cache depois: {cst}")
        with open(evfile, "a") as fh:
            fh.write(json.dumps(msg("again no report")) + "\n")
        outs = [json.loads(cphook("cp-stop", {})[1])["decision"] for _ in range(3)]
        check(outs == ["block", "allow", "allow"], f"pedidos de relatorio limitados: {outs}")
        os.remove(evfile)
        os.remove(os.path.join(cprun, "report-asks.json"))
        check(json.loads(cphook("cp-stop", {})[1]) == {"decision": "allow"},
              "sem stream legivel nao pede relatorio (nao prende o worker)")
        os.remove(os.path.join(cprun, "ctx.json"))
        rc, out = cphook("cp-pre", {"toolName": "view", "toolArgs": {"path": "src/a.txt"}})
        check(json.loads(out)["permissionDecision"] == "deny", "cp-pre quebrado nega")
        check(json.loads(cphook("cp-stop", {})[1]) == {"decision": "allow"}, "cp-stop quebrado deixa parar")
        cpev_log = guard_events(cprun)
        check(any(e.get("event") == "pre" and e.get("decision") == "deny" for e in cpev_log),
              "negacao do copilot registrada")

        # copilot hooks file: written for the run, ignored by the scope check, removed, never clobbered
        cpctx = dict(ctx, run_id="cprun")
        rel, made = install_cp_hooks(repo, cprun, cpctx)
        spec = read_json(os.path.join(repo, rel))
        check(rel == ".github/hooks/crew-cprun.json" and set(spec["hooks"]) ==
              {"sessionStart", "preToolUse", "agentStop"} and "cp-pre" in spec["hooks"]["preToolUse"][0]["bash"]
              and os.path.abspath(__file__) in spec["hooks"]["agentStop"][0]["bash"], "hooks do copilot gerados")
        check(rel in changed_paths(repo) and rel not in changed_paths(repo, [rel]), "escopo ignora so esse arquivo")
        check(fingerprint(repo, [], [rel]) != fingerprint(repo, []), "fingerprint ignora o arquivo de hooks")
        try:
            install_cp_hooks(repo, cprun, cpctx)
            check(False, "sobrescreveu o hooks do copilot")
        except Refusal:
            check(True, "recusa sobrescrever")
        try:
            refuse_cp_leftovers(repo)
            check(False, "sobra do copilot aceita")
        except Refusal as exc:
            check("rm " in str(exc), "sobra do copilot recusada com o rm")
        remove_cp_hooks(repo, rel, made)
        check(not os.path.exists(os.path.join(repo, ".github")), ".github criado pelo run removido")
        os.makedirs(os.path.join(repo, ".github", "hooks"))
        with open(os.path.join(repo, ".github", "hooks", "mine.json"), "w") as fh:
            fh.write("{}")
        check(refuse_cp_leftovers(repo) == [".github/hooks/mine.json"], "hooks do repo listados")
        rel, made = install_cp_hooks(repo, cprun, cpctx)
        remove_cp_hooks(repo, rel, made)
        check(made == [] and os.path.exists(os.path.join(repo, ".github", "hooks", "mine.json")),
              "diretorio existente e arquivo do usuario intocados")
        shutil.rmtree(os.path.join(repo, ".github"))

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
        # agy 1.4.2 (2026-10-18) adds Argon as its own group; on a Pro plan it is a separate quota
        argon = {"name": "Gemini 4 Argon", "description": "For paid Pro plans, Argon quota is separate. Higher "
                 "Argon quota (included as part of the larger Gemini quota bucket) is available on Ultra plans.",
                 "buckets": [{"name": "Gemini 4 Argon Weekly Limit", "remaining_fraction": 0.01,
                              "reset_time": "2026-10-25T01:46:00Z"}]}
        groups = usage["command"]["data"]["groups"]
        groups.append(argon)
        check(evaluate_quota(usage, "gemini-3.8-flash-high", 0.05) is None, "argon esgotado nao barra o flash")
        msg = evaluate_quota(usage, "gemini-4-argon-medium", 0.05)
        check(msg and "Gemini 4 Argon" in msg, "argon esgotado barra o argon")
        argon["buckets"][0]["remaining_fraction"] = 0.9
        groups[0]["buckets"][0]["remaining_fraction"] = 0
        check(evaluate_quota(usage, "gemini-4-argon-high", 0.05) is None, "flash esgotado nao barra o argon")
        check(evaluate_quota(usage, "gemini-3.8-flash-low", 0.05), "flash esgotado barra o flash")
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
        check(set(spec["crew"]) == {"SessionStart", "PreToolUse", "Stop"}, "hooks.json gerado")
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
    p = argparse.ArgumentParser(prog="crew.py", description=__doc__.split("\n\n")[0])
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
    r.add_argument("--copilot-model-override", action="store_true",
                   help="so copilot: aceita modelo diferente de auto (plano pago; nao testado)")
    gt = sub.add_parser("gate", help="roda o gate de uma task na arvore atual")
    gt.add_argument("task")
    gt.add_argument("--repo")
    gt.add_argument("--baseline", action="store_true",
                    help="so os comandos de format/checks, sem escopo nem forbid")
    h = sub.add_parser("hook", help="handler de hook do agy (instalado por run)")
    h.add_argument("event", choices=["pre", "stop", "start", "oc-pre", "cp-pre", "cp-stop"])
    h.add_argument("--state", required=True)
    a = p.parse_args(argv)
    if a.cmd == "hook":
        return hook_main(a.event, a.state)
    try:
        return {"delegate": cmd_delegate, "review": cmd_review, "gate": cmd_gate}[a.cmd](a)
    except Refusal as exc:
        eprint(f"crew: recusado: {exc}")
        print(json.dumps({"ok": False, "refused": True, "failures": [str(exc)]}, ensure_ascii=False))
        return 2
    except KeyboardInterrupt:
        eprint("crew: interrompido; hooks removidos")
        return 130


if __name__ == "__main__":
    sys.exit(main())
