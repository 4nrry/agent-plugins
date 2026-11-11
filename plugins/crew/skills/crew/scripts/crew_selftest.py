#!/usr/bin/env python3
"""The self-test of crew.py, kept beside it so that crew.py stays well under
the size above which a plugin directory holds a file for review. Run it
through crew.py's own self-test flag, or run this file.
"""
import contextlib
import io
import json
import os
import shlex
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time

import crew


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
        example = os.path.join(os.path.dirname(os.path.abspath(crew.__file__)), "..", "references",
                               "task.example.json")
        t = crew.load_task(example)
        check(t["scope"] and t["gate"]["checks"], "task.example.json loads")
        check("Operating rules" in crew.compose_prompt(t, repo), "composed prompt has the rules")

        task = crew.normalize_task({"prompt": "x", "scope": ["src/*"], "side_effects": ["side.json"],
                               "gate": {"format": ["ls -- {files} >/dev/null"], "checks": ["true"],
                                        "forbid": [r"@ts-ignore"]}})
        for bad, why in ((dict(prompt="", scope=["a"], gate={"checks": ["true"]}), "empty prompt"),
                         (dict(prompt="x", scope=[], gate={"checks": ["true"]}), "empty scope"),
                         (dict(prompt="x", scope=["../a"], gate={"checks": ["true"]}), "scope with .."),
                         (dict(prompt="x", scope=["a"], gate={}), "gate without commands"),
                         (dict(prompt="x", scope=["a"], gate={"checks": ["t"]},
                               report_schema={"type": "string"}), "schema without object root")):
            try:
                crew.normalize_task(bad)
                check(False, f"invalid task accepted: {why}")
            except crew.Refusal:
                check(True, why)

        ctx = crew.base_ctx(repo, task, "delegate")
        pre = lambda name, **args: crew.decide_pre({"toolCall": {"name": name, "args": args}}, ctx)  # noqa: E731
        check(pre("view_file", AbsolutePath=f"{repo}/src/a.txt")["decision"] == "allow", "read inside the repo")
        check(pre("read_file", Path=f"{repo}/src/a.txt")["decision"] == "allow", "agy 1.4.4 read_file in repo")
        check(pre("read_file", Path="/etc/passwd")["decision"] == "deny", "agy 1.4.4 read_file outside")
        check(pre("read_file", Path=f"{repo}/.env")["decision"] == "deny", "agy 1.4.4 read_file secret")
        check(pre("write_file", Path=f"{repo}/side.json", Overwrite=True)["decision"] == "deny",
              "agy 1.4.4 write_file out of scope")
        check(pre("edit_file", Path="src/../.git/config", Target="a", Replacement="b")["decision"] == "deny",
              "agy 1.4.4 edit_file into .git")
        check(pre("view_file", AbsolutePath="/etc/passwd")["decision"] == "deny", "read outside the repo")
        check(pre("list_dir", DirectoryPath="~/.claude")["decision"] == "deny", "home denied")
        check(pre("run_command", CommandLine="cat /tmp/x")["decision"] == "deny", "/tmp denied")
        check(pre("run_command", CommandLine="ls ..")["decision"] == "deny", ".. denied")
        check(pre("run_command", CommandLine="ps aux")["decision"] == "deny", "ps denied")
        check(pre("run_command", CommandLine="git commit -m x")["decision"] == "deny", "commit denied")
        check(pre("run_command", CommandLine="npm install left-pad")["decision"] == "deny", "install denied")
        check(pre("run_command", CommandLine="sed -i s/a/b/ src/a.txt")["decision"] == "deny", "sed -i denied")
        check(pre("run_command", CommandLine="echo $HOME")["decision"] == "deny", "$HOME denied")
        check(pre("run_command", CommandLine="npm test 2>&1 > /dev/null")["decision"] == "allow", "npm test")
        check(pre("run_command", CommandLine="git diff HEAD")["decision"] == "allow", "git diff allowed")
        check(pre("run_command", CommandLine="echo $((4 / 2))")["decision"] == "allow", "division is not a path")
        check(pre("run_command", CommandLine="sed -n 1,5p src/a.txt")["decision"] == "allow", "sed -n")
        # secrets: by tool and by shell, .env.example still readable, [] turns it off
        check(pre("view_file", AbsolutePath=f"{repo}/.env")["decision"] == "deny", "secret: view .env")
        check(pre("view_file", AbsolutePath=f"{repo}/apps/web/.dev.vars")["decision"] == "deny",
              "secret: .dev.vars")
        check(pre("view_file", AbsolutePath=f"{repo}/.env.example")["decision"] == "allow",
              "secret: .env.example allowed")
        check(pre("run_command", CommandLine="cat .env")["decision"] == "deny", "secret: cat .env")
        check(pre("run_command", CommandLine="grep DATABASE apps/api/.env.production")["decision"]
              == "deny", "secret: grep in .env.production")
        check(pre("run_command", CommandLine="cat certs/server.pem")["decision"] == "deny", "secret: pem")
        check(pre("run_command", CommandLine="node scripts/env-check.js")["decision"] == "allow",
              "secret: similar name is not a secret")
        nosec = dict(ctx, secret_globs=[])
        check(crew.decide_pre({"toolCall": {"name": "view_file", "args": {"AbsolutePath": f"{repo}/.env"}}},
                         nosec)["decision"] == "allow", "secret: empty list turns it off")
        # WaitMsBeforeAsync is no longer overwritten: it did not keep the command in the foreground
        check(pre("run_command", CommandLine="npm test") == {"decision": "allow"}, "run_command without overwrite")
        check("overwrite" not in pre("view_file", AbsolutePath=f"{repo}/src/a.txt"), "no overwrite outside the shell")
        check(pre("write_to_file", TargetFile=f"{repo}/src/b.txt", CodeContent="/etc/x")["decision"]
              == "allow", "write in scope; content is not scanned")
        check(pre("write_to_file", TargetFile=f"{repo}/side.json")["decision"] == "deny", "out of scope")
        check(pre("write_file", Path=f"{repo}/src/b.txt", Content="/etc/x", Overwrite=True)["decision"]
              == "allow", "agy 1.4.4 write_file in scope, path-like content ignored")
        check(pre("edit_file", Path=f"{repo}/src/b.txt", Target="/etc/a", Replacement="/etc/b")["decision"]
              == "allow", "agy 1.4.4 edit_file in scope")
        check(pre("replace_file_content", TargetFile="src/../.git/config")["decision"] == "deny", ".git")
        check(pre("write_to_file", TargetFile="/tmp/out.txt")["decision"] == "deny", "write outside the repo")
        check(pre("invoke_subagent", Task="x")["decision"] == "deny", "subagent denied")
        check(pre("finish", files_changed=["/etc/passwd"])["decision"] == "allow", "finish is not scanned")
        check(pre("grep_search", SearchPath=repo, Query="/api/v1")["decision"] == "allow", "Query ignored")
        # tool allowlist: network, workflows, MCP and unknown tools are denied
        for tool in ("read_url_content", "search_web", "run_workflow", "manage_task", "mcp_foo_bar",
                     "ask_permission", "send_message"):
            check(pre(tool, Url="https://example.com/a")["decision"] == "deny", f"{tool} denied")
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
                          (("run_command", {"CommandLine": "cd && ls"}), "bare cd"),
                          (("run_command", {"CommandLine": "cat //etc/passwd"}), "//etc"),
                          (("run_command", {"CommandLine": "cat /*/passwd"}), "glob at root"),
                          (("run_command", {"CommandLine": "cat </etc/passwd"}), "redirect from /etc"),
                          (("run_command", {"CommandLine": "echo x>/home/x"}), "redirect to /home")):
            check(pre(args[0], **args[1])["decision"] == "deny", f"escape denied: {why}")
        check(pre("run_command", CommandLine="cd src && ls")["decision"] == "allow", "cd inside the repo")
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
            check(pre("run_command", CommandLine=c)["decision"] == "deny", f"shell denied: {c}")
        # read-only commands that used to be false positives
        for c in ("grep -rn '/api/v1' src", "sed -n '/foo/,/bar/p' src/a.txt", "git grep -n 'deploy' -- src",
                  "git log --grep=publish", "npx vitest run -t 'GET /orders'", "git -C . diff",
                  "git --no-pager log -n 3", "git diff HEAD -- src 2>&1", "grep -n '->' src/a.txt",
                  "npm test >/dev/null 2>&1", "ls .github .gitignore", "python3 -m unittest -v 2>&1 | tail -5",
                  "cat src/a.txt && echo ok"):
            check(pre("run_command", CommandLine=c)["decision"] == "allow", f"read allowed: {c}")
        # symlink inside the scope that points out of the repo
        os.symlink("/", os.path.join(repo, "src", "lnk"))
        check(pre("write_to_file", TargetFile=f"{repo}/src/lnk/home/x")["decision"] == "deny", "symlink")
        check(pre("write_to_file", TargetFile="src/lnk/home/x")["decision"] == "deny", "relative symlink")
        os.remove(os.path.join(repo, "src", "lnk"))
        dctx = dict(ctx, gate_commands=["docker compose run test", "{files}"])
        dpre = lambda c: crew.decide_pre({"toolCall": {"name": "run_command", "args": {"CommandLine": c}}}, dctx)  # noqa: E731
        check(dpre("docker compose run test")["decision"] == "allow", "gate command exempt")
        check(dpre("docker compose run test && git push")["decision"] == "deny", "chained command is not exempt")
        check(dpre("docker ps")["decision"] == "deny", "empty prefix does not exempt everything")
        check(dpre("docker compose run test 2>&1 >/dev/null")["decision"] == "allow", "gate with harmless redirect")
        for c in ("docker compose run test\ngit push origin main", "docker compose run test\rgit push",
                  "docker compose run test <(git push origin HEAD)", "docker compose run test --x $HOME",
                  "docker compose run test > src/../x", "docker compose run testX"):
            check(dpre(c)["decision"] == "deny", f"gate does not exempt: {c!r}")

        # opencode backend: task fields, and its tool calls judged by the same decide_pre
        check(task["backend"] == "agy" and task["model"] == crew.DEFAULT_MODEL, "default backend is agy")
        otask = crew.normalize_task({"prompt": "x", "scope": ["src/*"], "backend": "opencode",
                                "gate": {"checks": ["true"]}})
        check(otask["model"] == crew.OPENCODE_DEFAULT_MODEL and not otask["disable_claude_code"],
              "opencode: default model and CLAUDE.md loaded")
        for bad, why in ((dict(prompt="x", scope=["a"], gate={"checks": ["t"]}, backend="hermes"), "backend"),
                         (dict(prompt="x", scope=["*"], gate={"checks": ["t"]}, backend="opencode"),
                          "scope covers opencode.json"),
                         (dict(prompt="x", scope=["a"], gate={"checks": ["t"]}, disable_claude_code="1"),
                          "disable_claude_code not boolean")):
            try:
                crew.normalize_task(bad)
                check(False, f"invalid task accepted: {why}")
            except crew.Refusal:
                check(True, why)
        check("ONE JSON object" in crew.compose_prompt(otask, repo) and "ONE JSON object" not in
              crew.compose_prompt(task, repo), "report rule only in the opencode prompt")
        octx = crew.base_ctx(repo, otask, "delegate")
        oc = lambda tool, **args: crew.decide_oc({"tool": tool, "args": args}, octx)["decision"]  # noqa: E731
        for tool, args, want, why in (
                ("read", {"filePath": f"{repo}/src/a.txt"}, "allow", "read inside the repo"),
                ("read", {"filePath": "/etc/passwd"}, "deny", "read outside the repo"),
                ("list", {"path": "../.."}, "deny", "list .."),
                ("glob", {"pattern": "/etc/*"}, "deny", "absolute glob"),
                ("glob", {"pattern": "src/**/*.ts"}, "allow", "glob inside the repo"),
                ("grep", {"pattern": "/api/v1", "path": "src"}, "allow", "grep regex is not a path"),
                ("write", {"filePath": f"{repo}/src/b.txt", "content": "/etc/x"}, "allow", "write in scope"),
                ("write", {"filePath": f"{repo}/top.txt", "content": "x"}, "deny", "write out of scope"),
                ("edit", {"filePath": "side.json", "oldString": "a", "newString": "b"}, "deny", "edit outside scope"),
                ("bash", {"command": "echo x > top.txt", "description": "w"}, "deny", "redirect"),
                ("bash", {"command": "printf x >> src/a.txt"}, "deny", "redirect even in scope"),
                ("bash", {"command": "cp src/a.txt top.txt"}, "deny", "cp in opencode"),
                ("bash", {"command": "cd src && touch x"}, "deny", "touch in opencode"),
                ("bash", {"command": "ls", "workdir": "/"}, "deny", "workdir outside"),
                ("bash", {"command": "python3 -m unittest 2>&1", "description": "Run /etc tests"},
                 "allow", "description is not a path"),
                ("bash", {"command": "git commit -m x"}, "deny", "commit"),
                ("apply_patch", {"patchText": "*** Begin Patch\n*** Update File: src/a.txt\n@@\n-a\n+b\n"
                                 "*** End Patch"}, "allow", "patch in scope"),
                ("apply_patch", {"patchText": "*** Add File: top.txt\n+x\n"}, "deny", "patch outside scope"),
                ("apply_patch", {"patchText": "*** Update File: src/a.txt\n*** Move to: ../x\n"}, "deny",
                 "patch moves outside"),
                ("apply_patch", {"patchText": "garbage"}, "deny", "patch without target"),
                ("todowrite", {"todos": []}, "allow", "todowrite inert"),
                ("webfetch", {"url": "https://example.com"}, "deny", "webfetch"),
                ("task", {"prompt": "x", "subagent_type": "general"}, "deny", "subagent"),
                ("batch", {"tool_calls": []}, "deny", "batch"),
                ("brand_new_tool", {}, "deny", "unknown tool")):
            check(oc(tool, **args) == want, f"opencode {why}: {tool} {args}")
        check(crew.decide_oc({"tool": "bash", "args": {"command": "cp a b"}}, ctx)["decision"] == "allow",
              "cp is still allowed in agy (agy policy unchanged)")
        rctx = dict(octx, scope=[], deny_patterns=crew.REVIEW_DENY_ALL)
        check(crew.decide_oc({"tool": "bash", "args": {"command": "ls"}}, rctx)["decision"] == "deny",
              "opencode review denies all shell")
        check(crew.decide_oc({"tool": "write", "args": {"filePath": "src/a.txt"}}, rctx)["decision"] == "deny",
              "opencode review denies writes")

        # copilot backend: model rule, task fields, tool translation to the same decide_pre
        ctask = crew.normalize_task({"prompt": "x", "scope": ["src/*"], "backend": "copilot",
                                "gate": {"checks": ["true"]}})
        check(ctask["model"] == "auto" and ctask["max_ai_credits"] == crew.COPILOT_MIN_AI_CREDITS,
              "copilot: auto model and 30-credit backstop")
        for bad, why in ((dict(model="gpt-5.6-luna"), "fixed model without override"),
                         (dict(model="claude-sonnet-5.5", copilot_model_override="yes"), "override not boolean"),
                         (dict(max_ai_credits=10), "max_ai_credits below 30"),
                         (dict(max_gate_attempts=9), "more attempts than the block limit"),
                         (dict(scope=["*"]), "scope covers .github/hooks"),
                         (dict(scope=[".claude/*"]), "scope covers .claude/settings.json")):
            try:
                crew.normalize_task({"prompt": "x", "scope": ["src/*"], "backend": "copilot",
                                "gate": {"checks": ["true"]}, **bad})
                check(False, f"invalid copilot task accepted: {why}")
            except crew.Refusal as exc:
                check(why != "fixed model without override" or "Free" in str(exc), f"{why}: {exc}")
        check(crew.normalize_task({"prompt": "x", "scope": ["src/*"], "backend": "copilot", "gate": {"checks": ["t"]},
                              "model": "claude-sonnet-5.5", "copilot_model_override": True})["model"]
              == "claude-sonnet-5.5", "override allows another model")
        check(crew.copilot_model_problem("auto", False) is None and crew.copilot_model_problem("x", False),
              "model rule")
        cprompt = crew.compose_prompt(ctask, repo)
        check("NO shell" in cprompt and "Run the format and check commands yourself" not in cprompt
              and "ONE JSON object" in cprompt and "after gate feedback" in cprompt,
              "copilot prompt: no shell, automatic gate, report in every final message")
        check("Run the format and check commands yourself" in crew.compose_prompt(task, repo), "agy prompt untouched")
        # codex: tool translation, decisions, stop gate, hook output, inline-hook TOML
        xtask = crew.normalize_task({"prompt": "x", "scope": ["src/*"], "backend": "codex", "effort": "low",
                                "gate": {"checks": ["true"]}})
        check(xtask["model"] == crew.CODEX_DEFAULT_MODEL and xtask["effort"] == "low", "codex task defaults")
        check("ONE JSON object" in crew.compose_prompt(xtask, repo), "codex prompt asks for the report")
        xctx = crew.base_ctx(repo, xtask, "delegate")
        cx = lambda tool, inp: crew.decide_cx({"tool_name": tool, "tool_input": inp}, xctx)["decision"]  # noqa: E731
        patch = lambda op, f: f"*** Begin Patch\n*** {op} File: {f}\n+x\n*** End Patch"  # noqa: E731
        for tool, inp, want, why in (
                ("Bash", {"command": "ls src"}, "allow", "read-only shell in the repo"),
                ("Bash", {"command": "printf hi > src/a.txt"}, "deny", "shell redirect"),
                ("Bash", {"command": "cat /etc/passwd"}, "deny", "shell read outside the repo"),
                ("Bash", {"command": "git commit -am x"}, "deny", "git write"),
                ("apply_patch", {"command": patch("Add", "src/new.txt")}, "allow", "patch in scope"),
                ("apply_patch", {"command": patch("Update", "README.md")}, "deny", "patch out of scope"),
                ("apply_patch", {"command": patch("Add", ".env")}, "deny", "patch on a secret"),
                ("apply_patch", {"command": "garbage"}, "deny", "unparsed patch"),
                ("mcp__fs__read", {}, "deny", "MCP tool"),
                ("update_plan", {"plan": []}, "allow", "inert tool")):
            check(cx(tool, inp) == want, f"codex {why}: expected {want}")
        check(crew.cx_hook_output("cx-pre", {"decision": "allow"}) == "", "codex allow prints nothing")
        dj = json.loads(crew.cx_hook_output("cx-pre", {"decision": "deny", "reason": "r"}))
        check(dj["hookSpecificOutput"]["permissionDecision"] == "deny", "codex deny shape")
        check(json.loads(crew.cx_hook_output("cx-stop", {"decision": "block", "reason": "go"}))["decision"] == "block",
              "codex stop block shape")
        import tomllib
        hargs = crew.codex_hooks_args("/tmp/run dir", 900)
        parsed = [tomllib.loads(hargs[i + 1]) for i in range(0, len(hargs), 2)]
        check(sorted(k for d in parsed for k in d["hooks"]) == ["PreToolUse", "SessionStart", "Stop"]
              and parsed[2]["hooks"]["Stop"][0]["hooks"][0]["timeout"] == 900
              and "cx-stop" in parsed[2]["hooks"]["Stop"][0]["hooks"][0]["command"], "codex -c hooks are TOML")
        xcmd = crew.codex_cmd("codex", "P", xtask, "/tmp/r", xctx)
        check("--dangerously-bypass-hook-trust" in xcmd and xcmd[xcmd.index("-s") + 1] == "workspace-write"
              and 'model_reasoning_effort="low"' in xcmd and xcmd[-1] == "P", "codex command")
        f_ok, info = crew.evaluate_cx(0, '{"type":"thread.started","thread_id":"t"}\n'
                                    '{"type":"item.completed","item":{"type":"agent_message","text":"done"}}\n'
                                    '{"type":"turn.completed","usage":{}}', "")
        check(not f_ok and info["text"] == "done" and info["thread_id"] == "t", "codex evaluation")
        check(crew.evaluate_cx(0, '{"type":"thread.started","thread_id":"t"}', "")[0], "codex cut turn fails")
        # grok: tool translation, run-gated hooks, closing Stop, command, evaluation
        gtask = crew.normalize_task({"prompt": "x", "scope": ["src/*"], "backend": "grok", "gate": {"checks": ["true"]}})
        check(gtask["model"] == crew.GROK_DEFAULT_MODEL, "grok default model")
        gctx = crew.base_ctx(repo, gtask, "delegate")
        gdir = os.path.join(tmp, "gk-run")
        os.makedirs(gdir, exist_ok=True)
        gk = lambda tool, inp: crew.decide_gk({"tool_name": tool, "tool_input": inp}, gctx)["decision"]  # noqa: E731
        for tool, inp, want, why in (
                ("read_file", {"target_file": "src/a.txt"}, "allow", "read in the repo"),
                ("read_file", {"target_file": "/etc/passwd"}, "deny", "read outside the repo"),
                ("list_dir", {"target_directory": "."}, "allow", "list the repo"),
                ("grep", {"pattern": "x", "path": "."}, "allow", "grep the repo"),
                ("write", {"file_path": "src/new.txt", "content": "x"}, "allow", "write in scope"),
                ("write", {"file_path": "README.md", "content": "x"}, "deny", "write out of scope"),
                ("search_replace", {"file_path": "src/a.txt", "old_string": "a", "new_string": "b"}, "allow",
                 "edit in scope"),
                ("search_replace", {"file_path": ".env", "old_string": "a", "new_string": "b"}, "deny",
                 "edit a secret"),
                ("run_terminal_command", {"command": "ls src"}, "allow", "read-only shell"),
                ("run_terminal_command", {"command": "printf hi > src/a.txt"}, "deny", "shell redirect"),
                ("ai-memory__memory_handoff_list", {}, "deny", "MCP tool"),
                ("web_fetch", {"url": "https://x"}, "deny", "tool outside the allowlist"),
                ("todo_write", {"todos": []}, "allow", "inert tool")):
            check(gk(tool, inp) == want, f"grok {why}: expected {want}")
        check(crew.cx_stop(gdir, gctx, {"stop_hook_active": False})["decision"] == "allow",
              "grok closing Stop without a message is never blocked")
        gcmd = crew.grok_cmd("grok", "P", dict(gtask, effort="low"))
        check(gcmd[gcmd.index("--sandbox") + 1] == "workspace" and "--no-subagents" in gcmd
              and gcmd[gcmd.index("--tools") + 1] == crew.GROK_TOOLS and gcmd[-1] == "low", "grok command")
        check(crew.grok_cmd("grok", "P", gtask)[-2:] == ["--reasoning-effort", crew.GROK_DEFAULT_EFFORT], "grok default effort")
        # --tools takes tool IDs (the shell is run_terminal_cmd); hooks see the shown names
        check("run_terminal_cmd" in crew.GROK_TOOLS.split(",") and "run_terminal_command" not in crew.GROK_TOOLS.split(",")
              and "run_terminal_command" in crew.GK_TOOLS, "grok --tools uses IDs, the guard shown names")
        shown = set(crew.GK_TOOLS) | crew.GK_INERT_TOOLS
        init = json.dumps({"type": "system", "subtype": "init", "tools": sorted(shown) + ["use_tool"]})
        check(crew.grok_tool_warnings("", init, shown) == [], "grok offered exactly crew's tools: no warning")
        gw = crew.grok_tool_warnings('warning: --tools "run_terminal_command" names no tool, so other tools stay '
                                'available\n', json.dumps({"type": "system", "subtype": "init",
                                                           "tools": sorted(shown) + ["image_gen"]}), shown)
        check(len(gw) == 2 and "names no tool" in gw[0] and "image_gen" in gw[1], "grok tool drift warned")
        gf, ginfo = crew.evaluate_gk(0, '{"type":"assistant","session_id":"s","message":{"content":[{"type":"text","text":"done"}]}}\n'
                                   '{"type":"result","session_id":"s","is_error":false,"usage":{}}', "")
        check(not gf and ginfo["text"] == "done" and ginfo["session_id"] == "s", "grok evaluation")
        check(crew.evaluate_gk(0, '{"type":"assistant","message":{"content":[]}}', "")[0], "grok cut run fails")
        # preflight on a fake grok: an untrusted repo is no refusal (a headless run loads
        # crew's hooks anyway); it warns only when Grok would skip the repo's instructions
        gbin, grepo = os.path.join(tmp, "grok-bin"), os.path.join(tmp, "grok-repo")
        os.makedirs(gbin)
        os.makedirs(os.path.join(grepo, ".claude", "rules"))
        with open(os.path.join(gbin, "grok"), "w") as fh:
            fh.write(f"#!/bin/sh\ncat {shlex.quote(os.path.join(gbin, 'inspect.json'))}\n")
        os.chmod(os.path.join(gbin, "grok"), 0o755)

        def gk_pre(trusted, version=crew.TESTED_GROK_VERSION):
            crew.write_json(os.path.join(gbin, "inspect.json"), {"grokVersion": version, "projectTrusted": trusted})
            return crew.preflight_grok(grepo)[1]
        old_path = os.environ["PATH"]
        os.environ["PATH"] = gbin + os.pathsep + old_path
        try:
            check(gk_pre(False) == [], "grok preflight: untrusted repo without instruction files, no warning")
            for name in ("AGENTS.md", "CLAUDE.md", os.path.join(".claude", "rules", "style.md"), "notes.md"):
                with open(os.path.join(grepo, name), "w") as fh:
                    fh.write("x\n")
            gw = gk_pre(False)
            check(len(gw) == 1 and "its AGENTS.md, CLAUDE.md, .claude/rules/ (" in gw[0]
                  and "grok --trust inspect" in gw[0], "grok preflight: untrusted repo names the skipped instructions")
            check(gk_pre(True) == [], "grok preflight: trusted repo, no warning")
            check(len(gk_pre(True, "1.0.99")) == 1, "grok preflight: untested version warned")
        finally:
            os.environ["PATH"] = old_path
        saved_dir, crew.GROK_HOOK_DIR = crew.GROK_HOOK_DIR, os.path.join(tmp, "grok-hooks")
        try:
            hf = crew.install_gk_hooks(gdir, "run-x", 900)
            hj = crew.read_json(hf)
            check(sorted(hj["hooks"]) == ["PreToolUse", "SessionStart", "Stop"]
                  and "gk-stop" in hj["hooks"]["Stop"][0]["hooks"][0]["command"]
                  and hj["hooks"]["Stop"][0]["hooks"][0]["timeout"] == 900, "grok hooks file")
        finally:
            crew.GROK_HOOK_DIR = saved_dir
        # another Grok session (no or another CREW_RUN) gets a silent allow from this run's hooks
        crew.write_json(os.path.join(gdir, "ctx.json"), dict(gctx, run_id="run-x"))
        for env_run, want in ((None, ""), ("other", ""), ("run-x", "deny")):
            e = dict(os.environ)
            e.pop(crew.RUN_ENV, None)
            if env_run:
                e[crew.RUN_ENV] = env_run
            pr = subprocess.run([sys.executable, os.path.realpath(crew.__file__), "hook", "gk-pre", "--state", gdir],
                                input=json.dumps({"tool_name": "write", "tool_input": {"file_path": "README.md"}}),
                                capture_output=True, text=True, env=e, timeout=60)
            got = json.loads(pr.stdout)["hookSpecificOutput"]["permissionDecision"] if pr.stdout.strip() else ""
            check(got == want, f"grok hook with CREW_RUN={env_run}: expected {want or 'no-op'}")
        # claude: tool translation, .claude/ protection, explicit allow, settings file, command, evaluation
        ltask = crew.normalize_task({"prompt": "x", "scope": ["src/*"], "backend": "claude", "gate": {"checks": ["true"]}})
        check(ltask["model"] == crew.CLAUDE_DEFAULT_MODEL, "claude default model")
        try:
            crew.normalize_task({"prompt": "x", "scope": ["src/*"], "backend": "claude", "effort": "ultra",
                            "gate": {"checks": ["t"]}})
            check(False, "claude effort ultra accepted")
        except crew.Refusal:
            check(True, "")
        lctx = crew.base_ctx(repo, ltask, "delegate")
        cl = lambda tool, inp: crew.decide_cl({"tool_name": tool, "tool_input": inp}, lctx)["decision"]  # noqa: E731
        for tool, inp, want, why in (
                ("Read", {"file_path": f"{repo}/src/a.txt"}, "allow", "read in the repo"),
                ("Read", {"file_path": "/etc/passwd"}, "deny", "read outside the repo"),
                ("Glob", {"pattern": "src/**"}, "allow", "glob the repo"),
                ("Grep", {"pattern": "x", "path": "src"}, "allow", "grep the repo"),
                ("Write", {"file_path": f"{repo}/src/new.txt", "content": "x"}, "allow", "write in scope"),
                ("Write", {"file_path": f"{repo}/README.md", "content": "x"}, "deny", "write out of scope"),
                ("Write", {"file_path": f"{repo}/.claude/settings.json", "content": "{}"}, "deny",
                 "write Claude settings"),
                ("Edit", {"file_path": f"{repo}/src/a.txt", "old_string": "a", "new_string": "b"}, "allow",
                 "edit in scope"),
                ("Edit", {"file_path": f"{repo}/.env", "old_string": "a", "new_string": "b"}, "deny", "edit a secret"),
                ("Bash", {"command": "ls src", "description": "list"}, "allow", "read-only shell"),
                ("Bash", {"command": "printf hi > src/a.txt"}, "deny", "shell redirect"),
                ("mcp__ai-memory__memory_query", {}, "deny", "MCP tool"),
                ("WebFetch", {"url": "https://x"}, "deny", "tool outside the allowlist"),
                ("Task", {"prompt": "x"}, "deny", "subagent"),
                ("TodoWrite", {"todos": []}, "allow", "inert tool")):
            check(cl(tool, inp) == want, f"claude {why}: expected {want}")
        check(json.loads(crew.cx_hook_output("cl-pre", {"decision": "allow"}))["hookSpecificOutput"][
              "permissionDecision"] == "allow", "claude allow is explicit (it approves Bash)")
        check(json.loads(crew.cx_hook_output("cl-stop", {"decision": "block", "reason": "go"}))["decision"] == "block",
              "claude Stop block")
        ldir = os.path.join(tmp, "cl-run")
        os.makedirs(ldir, exist_ok=True)
        lj = crew.read_json(crew.write_cl_settings(ldir, 900))
        check(sorted(lj["hooks"]) == ["PreToolUse", "SessionStart", "Stop"]
              and "cl-stop" in lj["hooks"]["Stop"][0]["hooks"][0]["command"]
              and lj["hooks"]["Stop"][0]["hooks"][0]["timeout"] == 900, "claude settings file")
        # the real hook command: argparse exits 2 on an unknown event, which Claude reads as a block
        crew.write_json(os.path.join(ldir, "ctx.json"), dict(lctx, run_id="run-l"))
        for inp, want in (({"file_path": f"{repo}/README.md", "content": "x"}, "deny"),
                          ({"file_path": f"{repo}/src/new.txt", "content": "x"}, "allow")):
            pr = subprocess.run([sys.executable, os.path.realpath(crew.__file__), "hook", "cl-pre", "--state", ldir],
                                input=json.dumps({"tool_name": "Write", "tool_input": inp}),
                                capture_output=True, text=True, timeout=60)
            got = json.loads(pr.stdout)["hookSpecificOutput"]["permissionDecision"] if pr.returncode == 0 else ""
            check(got == want, f"claude hook process: expected {want}")
        check('"checks_run"' in crew.compose_prompt(ltask, repo), "claude prompt carries the report schema")
        lcmd = crew.claude_cmd("claude", "P", dict(ltask, effort="low"), "/s.json")
        check("--restricted" in lcmd and lcmd[lcmd.index("--settings") + 1] == "/s.json"
              and lcmd[lcmd.index("--tools") + 1] == crew.CLAUDE_TOOLS and "--strict-mcp-config" in lcmd
              and lcmd[lcmd.index("--permission-mode") + 1] == "acceptEdits" and lcmd[-2:] == ["--effort", "low"],
              "claude command")
        lf, linfo = crew.evaluate_cl(0, '{"type":"result","subtype":"success","is_error":false,"result":"done",'
                                   '"session_id":"s","total_cost_usd":0.01}', "")
        check(not lf and linfo["text"] == "done" and linfo["session_id"] == "s" and linfo["cost_usd"] == 0.01,
              "claude evaluation")
        check(crew.evaluate_cl(0, "", "")[0], "claude cut run fails")
        check(crew.evaluate_cl(0, '{"type":"result","is_error":true,"result":"boom"}', "")[0], "claude error result fails")
        hostenv = dict(os.environ, CLAUDECODE="1")
        saved_env = dict(os.environ)
        try:
            os.environ.clear()
            os.environ.update(hostenv)
            crew.preflight_claude()
            check(False, "claude worker accepted inside Claude Code")
        except crew.Refusal:
            check(True, "")
        finally:
            os.environ.clear()
            os.environ.update(saved_env)
        # cursor: tool translation, .cursor/ protection, hooks file in the tree, command, evaluation
        utask = crew.normalize_task({"prompt": "x", "scope": ["src/*"], "backend": "cursor", "gate": {"checks": ["true"]}})
        check(utask["model"] == crew.CURSOR_DEFAULT_MODEL, "cursor default model")
        try:
            crew.normalize_task({"prompt": "x", "scope": ["*"], "backend": "cursor", "gate": {"checks": ["t"]}})
            check(False, "cursor scope covering .cursor/hooks.json accepted")
        except crew.Refusal:
            check(True, "")
        uctx = crew.base_ctx(repo, utask, "delegate")
        cu = lambda tool, inp: crew.decide_cu({"tool_name": tool, "tool_input": inp}, uctx)["decision"]  # noqa: E731
        for tool, inp, want, why in (
                ("Read", {"file_path": f"{repo}/src/a.txt"}, "allow", "read in the repo"),
                ("Read", {"file_path": "/etc/passwd"}, "deny", "read outside the repo"),
                ("List", {"file_path": "."}, "allow", "list the repo"),
                ("Grep", {"pattern": "x", "file_path": "src"}, "allow", "grep the repo"),
                ("Write", {"file_path": "src/new.txt", "content": "x"}, "allow", "write in scope"),
                ("Write", {"file_path": "README.md", "content": "x"}, "deny", "write out of scope"),
                ("Write", {"file_path": ".cursor/hooks.json", "content": "{}"}, "deny", "write the run's hooks"),
                ("Delete", {"file_path": "src/a.txt"}, "allow", "delete in scope"),
                ("Shell", {"command": "ls src", "cwd": ""}, "allow", "read-only shell"),
                ("Shell", {"command": "printf hi > src/a.txt", "cwd": ""}, "deny", "shell redirect"),
                ("Fetch", {"url": "https://x"}, "deny", "tool outside the allowlist"),
                ("ReadLints", {}, "allow", "inert tool")):
            check(cu(tool, inp) == want, f"cursor {why}: expected {want}")
        ucmd = crew.cursor_cmd("cursor-agent", "P", dict(utask, model="grok-4.7", effort="xhigh"), "chat-1")
        check(ucmd[ucmd.index("--model") + 1] == "grok-4.7-xhigh" and ucmd[-2:] == ["--resume", "chat-1"]
              and ucmd[ucmd.index("--sandbox") + 1] == "disabled", "cursor command")
        check(crew.cursor_cmd("cursor-agent", "P", dict(utask, model="auto", effort="high"), None)[-1] == "auto",
              "cursor: no effort suffix on auto")
        uf, uinfo = crew.evaluate_cu(0, '{"type":"system","subtype":"init","session_id":"c1"}\n'
                                   '{"type":"result","subtype":"success","is_error":false,"result":"done","session_id":"c1"}', "")
        check(not uf and uinfo["text"] == "done" and uinfo["session"] == "c1", "cursor evaluation")
        check(crew.evaluate_cu(0, '{"type":"system","subtype":"init","session_id":"c1"}', "")[0], "cursor cut run fails")
        ucreated = crew.install_cu_hooks(repo, os.path.join(tmp, "cu-run"))
        uspec = crew.read_json(os.path.join(repo, crew.CURSOR_HOOK_FILE))
        check(uspec["version"] == 1 and uspec["hooks"]["preToolUse"][0]["failClosed"] is True,
              "cursor hooks file: failClosed preToolUse")
        check(crew.changed_paths(repo, [crew.CURSOR_HOOK_FILE]) == [], "cursor hooks file is not a change")
        crew.remove_cu_hooks(repo, ucreated)
        check(not os.path.exists(os.path.join(repo, ".cursor")), ".cursor removed")
        cctx = crew.base_ctx(repo, ctask, "delegate")
        cp = lambda tool, args: crew.decide_cp({"toolName": tool, "toolArgs": args}, cctx)["decision"]  # noqa: E731
        for tool, args, want, why in (
                ("view", {"path": f"{repo}/src/a.txt"}, "allow", "view inside the repo"),
                ("view", {"path": "src/a.txt", "view_range": [1, 5]}, "allow", "relative view"),
                ("view", {"path": "/etc/passwd"}, "deny", "view outside the repo"),
                ("view", {"path": f"{repo}/.env"}, "deny", "view of a secret"),
                ("view", json.dumps({"path": "/etc/passwd"}), "deny", "args as a JSON string"),
                ("glob", {"pattern": "src/**/*.ts"}, "allow", "glob inside the repo"),
                ("glob", {"pattern": "/etc/*"}, "deny", "absolute glob"),
                ("grep", {"pattern": "/api/v1", "path": "src", "glob": "*.ts"}, "allow", "regex is not a path"),
                ("grep", {"pattern": "x", "path": "../.."}, "deny", "grep outside"),
                ("apply_patch", "*** Begin Patch\n*** Add File: src/b.txt\n+x\n*** End Patch\n", "allow",
                 "patch in scope (raw string)"),
                ("apply_patch", "*** Begin Patch\n*** Add File: NOTES.txt\n+x\n*** End Patch\n", "deny",
                 "patch out of scope"),
                ("apply_patch", "*** Add File: ../NOTES.txt\n+x\n", "deny", "patch with .."),
                ("apply_patch", "*** Add File: src/../NOTES.txt\n+x\n", "deny", "patch src/.."),
                ("apply_patch", "*** Update File: src/a.txt\n*** Move to: /tmp/x\n", "deny", "patch moves outside"),
                ("apply_patch", "*** Add File: src/a.txt\n+x\n*** Add File: side.json\n+y\n", "deny",
                 "patch with one target outside"),
                ("apply_patch", "garbage", "deny", "patch without target"),
                ("apply_patch", "*** Add File: .github/hooks/crew-x.json\n+{}\n", "deny",
                 "patch on the hooks file"),
                ("create", {"path": "src/c.txt", "file_text": "see /etc/passwd"}, "allow", "create in scope"),
                ("create", {"path": "top.txt", "file_text": "x"}, "deny", "create out of scope"),
                ("edit", {"path": "src/a.txt", "old_str": "/a/", "new_str": "/b/"}, "allow", "edit in scope"),
                ("edit", {"path": "side.json", "old_str": "a", "new_str": "b"}, "deny", "edit outside scope"),
                ("bash", {"command": "ls"}, "deny", "bash always denied"),
                ("read_bash", {"shellId": "1"}, "deny", "read_bash denied"),
                ("task", {"prompt": "x"}, "deny", "subagent"),
                ("web_fetch", {"url": "https://example.com"}, "deny", "network"),
                ("github-mcp-server-list_issues", {"owner": "x"}, "deny", "GitHub MCP"),
                ("skill", {"skill": "x"}, "deny", "skill"),
                ("report_intent", {"intent": "Editing /etc"}, "allow", "report_intent inert"),
                ("brand_new_tool", {}, "deny", "unknown tool")):
            check(cp(tool, args) == want, f"copilot {why}: {tool} {args}")
        crctx = dict(cctx, scope=[], deny_patterns=crew.REVIEW_DENY_ALL, mode="review")
        check(crew.decide_cp({"toolName": "create", "toolArgs": {"path": "src/a.txt"}}, crctx)["decision"] == "deny",
              "copilot review denies writes")
        check(crew.decide_cp({"toolName": "view", "toolArgs": {"path": "src/a.txt"}}, crctx)["decision"] == "allow",
              "copilot review reads")
        check(crew.cp_hook_output("cp-pre", {"decision": "allow"}) == "", "copilot allow prints nothing")
        dj = json.loads(crew.cp_hook_output("cp-pre", {"decision": "deny", "reason": "r"}))
        check(dj == {"permissionDecision": "deny", "permissionDecisionReason": "r"}, "deny in copilot format")
        check(json.loads(crew.cp_hook_output("cp-stop", {"decision": "stop"})) == {"decision": "allow"},
              "stop becomes allow in copilot")

        # copilot events: exit 0 with failed work, shell, subagent, missing result
        def cpev(*evs):
            return "\n".join(json.dumps(e) for e in evs)
        tstart = lambda n: {"type": "tool.execution_start", "data": {"toolName": n, "arguments": "{}"}}  # noqa: E731
        msg = lambda c: {"type": "assistant.message", "data": {"content": c, "phase": "final_answer"}}  # noqa: E731
        res = lambda c=0: {"type": "result", "sessionId": "s1", "exitCode": c, "usage": {"premiumRequests": 2}}  # noqa: E731
        f, info = crew.evaluate_cp(0, cpev(tstart("view"), {"type": "tool.execution_complete", "data": {
            "success": False}}, msg('ok {"status": "done"}'), msg(""), res()), "")
        check(f == [] and info["session"] == "s1" and info["tools"] == {"view": 1} and info["tool_failures"] == 1
              and info["premium_requests"] == 2 and crew.extract_report(info["text"]) == {"status": "done"},
              f"good copilot stream: {f} {info}")
        f, _ = crew.evaluate_cp(0, cpev(tstart("bash"), res()), "")
        check(any("shell" in x for x in f), "bash call fails the run")
        f, _ = crew.evaluate_cp(0, cpev(tstart("task"), res()), "")
        check(any("subagent" in x for x in f), "task call fails the run")
        f, _ = crew.evaluate_cp(0, cpev(msg("x")), "")
        check(any("result" in x for x in f), "missing result fails the run")
        f, _ = crew.evaluate_cp(0, cpev(res(1)), "")
        check(any("exitCode" in x for x in f), "result with exitCode != 0 fails the run")
        f, _ = crew.evaluate_cp(1, cpev(res()), "boom")
        check(any("rc=1" in x for x in f), "rc != 0 fails the run")
        f, _ = crew.evaluate_cp(0, "", "")
        check(any("no JSON event" in x for x in f), "empty stdout fails the run")
        f, _ = crew.evaluate_cp(0, cpev({"type": "session.error", "data": {"message": "quota"}}, res()), "")
        check(any("session.error" in x for x in f), "error event fails the run")
        upath = os.path.join(tmp, "usage.json")
        crew.write_json(upath, {"totalPremiumRequestCost": 2, "totalNanoAiu": 939943800, "aiCreditsStatus": "complete",
                           "modelMetrics": {"gpt-5.6-luna": {}}, "currentModel": "gpt-5.6-luna"})
        u = crew.read_cp_usage(upath)
        check(u["ai_credits"] == 0.9399 and u["served_models"] == ["gpt-5.6-luna"] and u["premium_requests"] == 2,
              f"copilot usage: {u}")
        check(crew.read_cp_usage(os.path.join(tmp, "nope.json")) is None, "usage missing")
        cmdl = crew.copilot_cmd("copilot", "-x", "auto", "/r", crew.COPILOT_EXCLUDED_TOOLS, 30)
        i = cmdl.index("--excluded-tools")
        check(cmdl[i + 1:i + 3] == ["bash", "task"] and "--disallow-temp-dir" in cmdl and cmdl[2] == "Task:\n-x"
              and "--allow-all-paths" not in cmdl and "--allow-all" not in cmdl, "copilot command line")
        check(crew.copilot_env("rid")["COPILOT_ALLOW_ALL"] == "true" and crew.copilot_env("rid")[crew.RUN_ENV] == "rid"
              and crew.copilot_env("rid")["NX_DAEMON"] == "false", "copilot environment")

        # opencode events: exit 0 is never success
        sid = "ses_x"
        evs = lambda *e: "\n".join(json.dumps(dict(x, sessionID=sid)) for x in e)  # noqa: E731
        fin = lambda r: {"type": "step_finish", "part": {"reason": r, "tokens": {"input": 5, "output": 2},  # noqa: E731
                                                         "cost": 0}}
        txt = {"type": "text", "part": {"text": 'Done.\n```json\n{"status": "done", "x": {"y": 1}}\n```'}}
        f, info = crew.evaluate_oc(0, evs(fin("tool-calls"), txt, fin("stop")), "")
        check(f == [] and info["session"] == sid and info["tokens"]["input"] == 10, f"good stream: {f}")
        check(crew.extract_report(info["text"]) == {"status": "done", "x": {"y": 1}}, "report from a json block")
        f, _ = crew.evaluate_oc(0, evs(fin("tool-calls")), "")
        check(any("reason=stop" in x for x in f), "no final stop fails the run")
        f, info = crew.evaluate_oc(0, evs(fin("tool-calls"), txt), "")
        check(f == [] and crew.extract_report(info["text"]) == {"status": "done", "x": {"y": 1}},
              f"opencode 2.x: ending on the text event is success: {f}")
        f, _ = crew.evaluate_oc(0, evs({"type": "error", "error": {"name": "APIError", "data": {
            "message": "free tier"}}}), "")
        check(any("free tier" in x for x in f), "error event fails the run with exit 0")
        f, _ = crew.evaluate_oc(0, "", "")
        check(any("no JSON event" in x for x in f), "empty stdout fails the run")
        f, _ = crew.evaluate_oc(1, evs(fin("stop")), "boom")
        check(any("rc=1" in x for x in f), "rc != 0 fails the run")
        check(crew.extract_report('{"a": 1} then {"b": {"c": 2}}') == {"b": {"c": 2}}, "last top-level object")
        check(crew.extract_report("no json {here") is None, "no report")
        check(crew.report_problems(None, crew.DEFAULT_REPORT_SCHEMA) and crew.report_problems({"status": "done"},
              crew.DEFAULT_REPORT_SCHEMA), "report missing or incomplete")
        check(crew.oc_message("-rf") == "Task:\n-rf" and crew.oc_message("x") == "x", "message never becomes a flag")

        # opencode.json: exact bytes restored, a created one removed
        with open(os.path.join(repo, "opencode.json"), "wb") as fh:
            fh.write(b'{\n  "share": "disabled"\n}\n')
        snap = crew.snapshot_files(repo, crew.OPENCODE_CONFIG_FILES)
        with open(os.path.join(repo, "opencode.json"), "wb") as fh:
            fh.write(b'{\n  "$schema": "https://opencode.ai/config.json",\n  "share": "disabled"\n}\n')
        with open(os.path.join(repo, "opencode.jsonc"), "w") as fh:
            fh.write("{}")
        check(crew.restore_files(repo, snap) == {"opencode.json", "opencode.jsonc"}, "restores both")
        with open(os.path.join(repo, "opencode.json"), "rb") as fh:
            check(fh.read() == b'{\n  "share": "disabled"\n}\n', "original bytes")
        check(not os.path.exists(os.path.join(repo, "opencode.jsonc")), "created by the run and removed")
        check(crew.restore_files(repo, snap) == set(), "restoring again changes nothing")
        os.remove(os.path.join(repo, "opencode.json"))

        # the generated guard forwards to this script and holds no policy of its own
        grd = os.path.join(tmp, "g")
        os.makedirs(grd)
        cfg = crew.write_oc_guard(grd)
        js = open(os.path.join(cfg, "plugins", "crew-guard.js"), encoding="utf-8").read()
        check(json.dumps(os.path.abspath(crew.__file__)) in js and '"oc-pre"' in js and "__" not in js
              and "export default" in js and '"execute.before"' in js,
              "generated guard: v2 shape, points at this script")
        env_oc = crew.opencode_env(cfg, False)
        check(env_oc["OPENCODE_CONFIG_DIR"] == cfg
              and json.loads(env_oc["OPENCODE_CONFIG_CONTENT"]) == {"permission": {"external_directory": "deny"}},
              "run config: guard through OPENCODE_CONFIG_DIR, external_directory deny")
        rid = f"selftest-{os.getpid()}"
        child = subprocess.Popen(["sleep", "60"], env={**os.environ, crew.RUN_ENV: rid},
                                 start_new_session=True)
        other = subprocess.Popen(["sleep", "60"], start_new_session=True)
        time.sleep(0.3)
        hit = crew.stop_run_procs(rid)
        child.wait(timeout=10)
        check(child.pid in hit and child.returncode is not None, "marked process stopped")
        check(other.poll() is None, "unmarked process untouched")
        other.kill()
        other.wait()
        check(crew.stop_run_procs("") == {}, "no run_id stops nothing")

        # BackgroundWatcher: who may be killed, from a synthetic tree (agy = 1)
        bw = crew.BackgroundWatcher(tmp, "rid")
        bw.baseline = {12}
        tree = {10: 1, 11: 10, 12: 1, 13: 12, 14: 1, 15: 1, 16: 1, 17: 14}
        info = {10: (f"{bw.hook_tag} stop --state x", True, False), 11: ("npx tsc", True, True),
                12: ("agy-helper", True, False), 13: ("node child-of-baseline", True, False),
                14: ("bash -c nx run web:typecheck", True, False), 15: ("sleep 9", False, False),
                16: ("uv tool uvx --from x kino --mcp", True, False), 17: ("node tsc", True, False)}
        check(set(bw.candidates(1, tree, info)) == {14, 17},
              "watcher: only the worker's marked command; hook, gate, baseline, MCP and unmarked stay")
        tree[1] = 0
        info[1] = ("agy -p", True, False)
        check(1 not in bw.candidates(1, tree, info), "watcher: never agy itself")

        # BackgroundWatcher: done only after a green gate
        def bw_events(*evs):
            d = tempfile.mkdtemp(dir=tmp)
            for e in evs:
                crew.append_jsonl(os.path.join(d, "guard.jsonl"), e)
            w = crew.BackgroundWatcher(d, "rid")
            w._read_events()
            return w
        green, red = {"event": "gate", "passed": True}, {"event": "gate", "passed": False}
        cmd_ev = {"event": "pre", "tool": "run_command", "decision": "allow"}
        check(bw_events(cmd_ev, green, {"event": "stop", "decision": "stop"}).finished_at,
              "watcher: Stop with green gate = finished")
        check(bw_events(green, {"event": "pre", "tool": "finish", "decision": "allow"}).finished_at,
              "watcher: finish allowed with green gate = finished")
        check(bw_events(red, {"event": "pre", "tool": "finish", "decision": "allow"}).finished_at is None,
              "watcher: finish with red gate does not count")
        check(bw_events(green, red, {"event": "stop", "decision": "stop"}).finished_at is None,
              "watcher: only the last gate counts")
        check(bw_events(cmd_ev, {"event": "stop", "decision": "continue"}).finished_at is None,
              "watcher: Stop with continue does not count")

        # BackgroundWatcher against real processes: a fake agy with a helper
        # started before the first command and a worker command after it
        wd = tempfile.mkdtemp(dir=tmp)
        flag = os.path.join(wd, "spawn")
        fake = subprocess.Popen(
            ["bash", "-c", f"sleep 60 & while [ ! -e {shlex.quote(flag)} ]; do sleep 0.05; done; "
                           "sleep 61 & env -u " + crew.RUN_ENV + " sleep 62 & wait"],
            env={**os.environ, crew.RUN_ENV: rid}, start_new_session=True)
        try:
            w = crew.BackgroundWatcher(wd, rid, grace=0.3)
            t0 = time.time()
            while time.time() - t0 < 5 and not any("sleep 60" in crew.proc_cmdline(p)
                                                   for p in crew.descendants(fake.pid, crew.ppid_map())
                                                   if os.path.exists(f"/proc/{p}")):
                time.sleep(0.05)
            w.poll(fake.pid)
            crew.append_jsonl(os.path.join(wd, "guard.jsonl"), cmd_ev)
            open(flag, "w").close()
            kids = {}
            t0 = time.time()
            # wait for the three sleeps by name: the fake agy's own bash is a
            # key too, and `env -u ...` shows its own cmdline until it execs
            while time.time() - t0 < 5 and not {"sleep 60", "sleep 61", "sleep 62"} <= kids.keys():
                time.sleep(0.05)
                kids = {}
                for p in crew.descendants(fake.pid, crew.ppid_map()):
                    try:
                        kids[crew.proc_cmdline(p)] = p
                    except OSError:
                        pass
            w.poll(fake.pid)
            check(w.finished_at is None and not w.killed, "watcher: nothing before the worker finishes")
            crew.append_jsonl(os.path.join(wd, "guard.jsonl"), green)
            crew.append_jsonl(os.path.join(wd, "guard.jsonl"), {"event": "stop", "decision": "stop"})
            w.poll(fake.pid)
            check(not w.killed, "watcher: waits for the grace period")
            time.sleep(0.4)
            w.poll(fake.pid)
            alive = {c: os.path.exists(f"/proc/{p}") for c, p in kids.items()}
            check(set(w.killed.values()) == {"sleep 61"} and not alive.get("sleep 61")
                  and alive.get("sleep 60") and alive.get("sleep 62") and fake.poll() is None,
                  f"watcher: only the worker's command stopped; helper, unmarked and agy alive ({w.killed}, {alive})")
            check(os.path.isfile(os.path.join(wd, "procs.jsonl")), "watcher: tree recorded in procs.jsonl")
        finally:
            os.killpg(fake.pid, signal.SIGKILL)     # our own fake agy's group
            fake.wait()
        check("OPENCODE_DISABLE_CLAUDE_CODE" in crew.opencode_env("/x.js", True)
              and "OPENCODE_DISABLE_CLAUDE_CODE" not in crew.opencode_env("/x.js", False), "CLAUDE.md flag")

        # gate: nothing changed -> fail; in-scope change -> pass; forbid; out of scope
        ok, text, _ = crew.run_gate(repo, ctx)
        check(not ok and "no file in the scope was changed" in text, "gate fails without a change")
        ok, text, _ = crew.run_gate(repo, ctx, baseline=True)
        check(ok and "skipped" in text, "baseline runs only commands")
        with open(os.path.join(repo, "src", "a.txt"), "a") as fh:
            fh.write("two\n")
        with open(os.path.join(repo, "src", "new file.txt"), "w") as fh:
            fh.write("ok\n")
        ok, text, cls = crew.run_gate(repo, ctx)
        check(ok, f"gate passes with an in-scope change: {text}")
        check(sorted(cls["in_scope"]) == ["src/a.txt", "src/new file.txt"], "classifies scope")
        with open(os.path.join(repo, "src", "a.txt"), "a") as fh:
            fh.write("x // @ts-ignore\n")
        ok, text, _ = crew.run_gate(repo, ctx)
        check(not ok and "src/a.txt:3" in text, f"forbid with line number: {text}")
        subprocess.run(g + ["checkout", "-q", "--", "src/a.txt"], check=True)
        with open(os.path.join(repo, "side.json"), "w") as fh:
            fh.write('{"analytics": false}\n')
        with open(os.path.join(repo, "other.txt"), "w") as fh:
            fh.write("x\n")
        ok, text, cls = crew.run_gate(repo, ctx)
        check(not ok and "other.txt" in text and cls["side_effects"] == ["side.json"],
              "out of scope fails; side effect tolerated")
        os.remove(os.path.join(repo, "other.txt"))
        ok, text, _ = crew.run_gate(repo, dict(ctx, gate=dict(ctx["gate"], checks=['test "$CREW_GATE" = 1'])))
        check(ok, "gate exports CREW_GATE")
        ctx2 = dict(ctx, gate=dict(ctx["gate"], checks=["false"]))
        ok, text, _ = crew.run_gate(repo, ctx2)
        check(not ok and "FAILED (rc=1)" in text, "failing check fails the gate")

        # fingerprint ignores side effects and changes with in-scope edits
        fp1 = crew.fingerprint(repo, ["side.json"])
        with open(os.path.join(repo, "side.json"), "w") as fh:
            fh.write('{"analytics": true}\n')
        check(crew.fingerprint(repo, ["side.json"]) == fp1, "fingerprint ignores side effects")
        with open(os.path.join(repo, "src", "new file.txt"), "a") as fh:
            fh.write("more\n")
        check(crew.fingerprint(repo, ["side.json"]) != fp1, "fingerprint changes with the scope")

        # hooks end to end through a subprocess: never `{}` for pre, gate cache
        rundir = os.path.join(tmp, "run")
        os.makedirs(rundir)
        crew.write_json(os.path.join(rundir, "ctx.json"), dict(ctx, max_gate_attempts=4))

        def hook(event, payload):
            p = subprocess.run([sys.executable, os.path.abspath(crew.__file__), "hook", event, "--state", rundir],
                               input=json.dumps(payload), capture_output=True, text=True, timeout=60)
            return json.loads(p.stdout)
        check(hook("start", {"modelName": "m"}) == {}, "start returns {}")
        check(hook("pre", {"toolCall": {"name": "view_file", "args": {"AbsolutePath": "/etc/x"}}})
              ["decision"] == "deny", "hook pre denies")
        check(hook("pre", {"toolCall": {"name": "list_dir", "args": {"DirectoryPath": repo}}})
              == {"decision": "allow"}, "hook pre allows explicitly")
        check(hook("oc-pre", {"tool": "write", "args": {"filePath": "/tmp/x", "content": "x"}})["decision"]
              == "deny", "hook oc-pre denies")
        check(hook("oc-pre", {"tool": "read", "args": {"filePath": f"{repo}/src/a.txt"}})
              == {"decision": "allow"}, "hook oc-pre allows explicitly")
        check(hook("oc-pre", {"tool": "read", "args": {"path": f"{repo}/src/a.txt"}})
              == {"decision": "allow"}, "opencode 2.x read {path} in repo")
        check(hook("oc-pre", {"tool": "read", "args": {"path": "/etc/passwd"}})["decision"] == "deny",
              "opencode 2.x read {path} outside")
        check(hook("oc-pre", {"tool": "write", "args": {"path": f"{repo}/side.json", "content": "x"}})
              ["decision"] == "deny", "opencode 2.x write {path} out of scope")
        check(hook("oc-pre", {"tool": "shell", "args": {"command": "cat /etc/passwd", "workdir": repo}})
              ["decision"] == "deny", "opencode 2.x shell outside the repo")
        check(hook("oc-pre", {"tool": "execute", "args": {"code": "fetch('https://x')"}})["decision"]
              == "deny", "opencode 2.x execute (JS sandbox) denied")
        r = hook("stop", {"terminationReason": "NO_TOOL_CALL"})
        check(r["decision"] == "continue" and "finish" in r["reason"],
              f"stop with green gate and no finish asks for the report: {r}")
        r = hook("pre", {"toolCall": {"name": "finish", "args": {}}})
        check(r["decision"] == "allow", "finish with green gate")
        st = crew.read_json(os.path.join(rundir, "gate-state.json"))
        check(st["attempts"] == 2 and st["runs"] == 1, f"gate cache: {st}")
        with open(os.path.join(repo, "outside.txt"), "w") as fh:
            fh.write("x\n")
        r = hook("stop", {"terminationReason": "TERMINAL_STEP_TYPE"})
        check(r["decision"] == "continue" and "outside.txt" in r["reason"], "stop with red gate continues")
        r = hook("stop", {"terminationReason": "MAX_INVOCATIONS"})
        check(r["decision"] == "stop", "other reasons stop without the gate")
        r = hook("pre", {"toolCall": {"name": "finish", "args": {}}})
        check(r["decision"] == "allow", "attempt limit releases finish")
        st = crew.read_json(os.path.join(rundir, "gate-state.json"))
        check(st["runs"] == 3, f"a failure never comes from the cache: {st}")
        with open(os.path.join(repo, "src", "nf.txt"), "w") as fh:
            fh.write("x\n")
        rd_save = rundir
        for name in ("nofinish", "finished"):
            rundir = os.path.join(tmp, name)
            os.makedirs(rundir)
            crew.write_json(os.path.join(rundir, "ctx.json"), dict(
                ctx, max_gate_attempts=9, gate=dict(ctx["gate"], format=[], checks=["true"]), scope=["*"]))
        rundir = os.path.join(tmp, "nofinish")
        got = [hook("stop", {"terminationReason": "NO_TOOL_CALL"})["decision"] for _ in range(crew.AGY_REPORT_ASKS + 1)]
        check(got == ["continue"] * crew.AGY_REPORT_ASKS + ["stop"], f"asks for finish at most {crew.AGY_REPORT_ASKS} times: {got}")
        rundir = os.path.join(tmp, "finished")
        hook("pre", {"toolCall": {"name": "finish", "args": {}}})
        r = hook("stop", {"terminationReason": "TERMINAL_STEP_TYPE"})
        check(r["decision"] == "stop", f"stop with green gate after finish stops: {r}")
        rundir = rd_save
        os.remove(os.path.join(repo, "src", "nf.txt"))
        os.remove(os.path.join(rundir, "ctx.json"))
        check(hook("pre", {"toolCall": {"name": "view_file", "args": {}}})["decision"] == "deny",
              "broken guard denies instead of returning {}")
        check(hook("stop", {})["decision"] == "stop", "broken stop lets it stop")
        check(hook("oc-pre", {"tool": "read", "args": {}})["decision"] == "deny", "broken oc-pre denies")
        events = crew.guard_events(rundir)
        check(any(e.get("event") == "session_start" for e in events), "SessionStart marker")

        # copilot hooks end to end: cp-pre output contract, gate and report on agentStop
        os.remove(os.path.join(repo, "outside.txt"))
        cprun = os.path.join(tmp, "cprun")
        os.makedirs(cprun)
        once = os.path.join(tmp, "gate-once")
        evfile = os.path.join(cprun, "copilot.stdout")
        crew.write_json(os.path.join(cprun, "ctx.json"), dict(
            ctx, max_gate_attempts=3, run_id="cprun", ignore_paths=[crew.cp_hook_rel("cprun")],
            events_file=evfile, report_schema={"type": "object", "required": ["status"]},
            gate=dict(ctx["gate"], format=[], checks=[f"test -e {shlex.quote(once)} || "
                                                      f"{{ touch {shlex.quote(once)}; false; }}"])))

        def cphook(event, payload):
            p = subprocess.run([sys.executable, os.path.abspath(crew.__file__), "hook", event, "--state", cprun],
                               input=json.dumps(payload), capture_output=True, text=True, timeout=60)
            return p.returncode, p.stdout.strip()
        rc, out = cphook("cp-pre", {"toolName": "view", "toolArgs": {"path": f"{repo}/src/a.txt"}})
        check(rc == 0 and out == "", f"cp-pre allow: empty output ({out!r})")
        rc, out = cphook("cp-pre", {"toolName": "apply_patch", "toolArgs": "*** Add File: ../x\n+x\n"})
        check(rc == 0 and json.loads(out)["permissionDecision"] == "deny", "cp-pre deny with a reason")
        with open(evfile, "w") as fh:
            fh.write(json.dumps(msg("done, no report")) + "\n")
        rc, out = cphook("cp-stop", {"stop_hook_active": False})
        check(json.loads(out)["decision"] == "block" and "gate FAILED" in json.loads(out)["reason"],
              f"agentStop with red gate blocks: {out}")
        rc, out = cphook("cp-stop", {"stop_hook_active": True})
        check(json.loads(out)["decision"] == "block" and "report" in json.loads(out)["reason"],
              f"green gate without report asks for the report: {out}")
        with open(evfile, "a") as fh:
            fh.write(json.dumps(msg('ok {"status": "done"}')) + "\n")
        rc, out = cphook("cp-stop", {"stop_hook_active": True})
        check(json.loads(out) == {"decision": "allow"}, f"green gate with report allows: {out}")
        cst = crew.read_json(os.path.join(cprun, "gate-state.json"))
        check(cst["runs"] == 2 and cst["attempts"] == 3, f"copilot gate: green cached afterwards: {cst}")
        with open(evfile, "a") as fh:
            fh.write(json.dumps(msg("again no report")) + "\n")
        outs = [json.loads(cphook("cp-stop", {})[1])["decision"] for _ in range(3)]
        check(outs == ["block", "allow", "allow"], f"report requests are limited: {outs}")
        os.remove(evfile)
        os.remove(os.path.join(cprun, "report-asks.json"))
        check(json.loads(cphook("cp-stop", {})[1]) == {"decision": "allow"},
              "no readable stream: no report request (does not trap the worker)")
        os.remove(os.path.join(cprun, "ctx.json"))
        rc, out = cphook("cp-pre", {"toolName": "view", "toolArgs": {"path": "src/a.txt"}})
        check(json.loads(out)["permissionDecision"] == "deny", "broken cp-pre denies")
        check(json.loads(cphook("cp-stop", {})[1]) == {"decision": "allow"}, "broken cp-stop lets it stop")
        cpev_log = crew.guard_events(cprun)
        check(any(e.get("event") == "pre" and e.get("decision") == "deny" for e in cpev_log),
              "copilot denial logged")

        # copilot hooks file: written for the run, ignored by the scope check, removed, never clobbered
        cpctx = dict(ctx, run_id="cprun")
        rel, made = crew.install_cp_hooks(repo, cprun, cpctx)
        spec = crew.read_json(os.path.join(repo, rel))
        check(rel == ".github/hooks/crew-cprun.json" and set(spec["hooks"]) ==
              {"sessionStart", "preToolUse", "agentStop"} and "cp-pre" in spec["hooks"]["preToolUse"][0]["bash"]
              and os.path.abspath(crew.__file__) in spec["hooks"]["agentStop"][0]["bash"], "copilot hooks generated")
        check(rel in crew.changed_paths(repo) and rel not in crew.changed_paths(repo, [rel]), "scope ignores only that file")
        check(crew.fingerprint(repo, [], [rel]) != crew.fingerprint(repo, []), "fingerprint ignores the hooks file")
        try:
            crew.install_cp_hooks(repo, cprun, cpctx)
            check(False, "overwrote the copilot hooks file")
        except crew.Refusal:
            check(True, "refuses to overwrite")
        try:
            crew.refuse_cp_leftovers(repo)
            check(False, "copilot leftover accepted")
        except crew.Refusal as exc:
            check("rm " in str(exc), "copilot leftover refused with the rm")
        crew.remove_cp_hooks(repo, rel, made)
        check(not os.path.exists(os.path.join(repo, ".github")), ".github created by the run removed")
        os.makedirs(os.path.join(repo, ".github", "hooks"))
        with open(os.path.join(repo, ".github", "hooks", "mine.json"), "w") as fh:
            fh.write("{}")
        check(crew.refuse_cp_leftovers(repo) == [".github/hooks/mine.json"], "repo hooks listed")
        rel, made = crew.install_cp_hooks(repo, cprun, cpctx)
        crew.remove_cp_hooks(repo, rel, made)
        check(made == [] and os.path.exists(os.path.join(repo, ".github", "hooks", "mine.json")),
              "existing directory and user file untouched")
        shutil.rmtree(os.path.join(repo, ".github"))

        # result evaluation: the exit-0 failure modes
        sch = crew.DEFAULT_REPORT_SCHEMA
        good = {"status": "SUCCESS", "structured_output": {"status": "done", "files_changed": [],
                "checks_run": [], "divergences": [], "out_of_scope_needs": []}}
        f, w, _ = crew.evaluate_run(0, json.dumps(good), "", "delegate", sch)
        check(f == [] and w == [], f"good run: {f}")
        f, _, _ = crew.evaluate_run(0, "", "", "delegate", sch)
        check(any("empty stdout" in x for x in f), "empty stdout")
        f, _, _ = crew.evaluate_run(0, json.dumps(dict(good, structured_output=None)), "", "delegate", sch)
        check(any("structured_output is null" in x for x in f), "schema not satisfied")
        f, _, _ = crew.evaluate_run(0, json.dumps(good), "[agy] print timeout after 5s with turn", "delegate", sch)
        check(any("timeout" in x for x in f), "timeout marker")
        den = dict(good, denied_actions=[{"action": "command"}])
        f, _, _ = crew.evaluate_run(0, json.dumps(den), "", "delegate", sch)
        check(any("denied_actions" in x for x in f), "denied_actions fails delegate")
        f, w, _ = crew.evaluate_run(0, json.dumps(dict(den, structured_output={"verdict": "approve",
                               "findings": [], "summary": ""})), "", "review", crew.DEFAULT_REVIEW_SCHEMA)
        check(f == [] and w, "denied_actions only warns in review")
        f, _, _ = crew.evaluate_run(1, "", "error: invalid model selection", "delegate", sch)
        check(any("rc=1" in x for x in f), "rc != 0")
        part = dict(good, structured_output=dict(good["structured_output"], status="partial"))
        f, _, _ = crew.evaluate_run(0, json.dumps(part), "", "delegate", sch)
        check(any("partial" in x for x in f), "partial worker fails the run")
        f, _, _ = crew.evaluate_run(0, json.dumps(dict(good, structured_output={"status": "done"})), "",
                               "delegate", sch)
        check(any("required fields" in x for x in f), "required fields")
        for bad in ("null", "[]", "3"):
            f, _, _ = crew.evaluate_run(0, bad, "", "delegate", sch)
            check(any("not an object" in x for x in f), f"envelope {bad} fails the run")

        # quota and models, against the shapes agy 1.3.4 printed on 2026-10-13
        usage = {"command": {"data": {"groups": [
            {"name": "Gemini Models", "description": "Models within this group: Gemini Flash, Gemini Pro",
             "buckets": [{"name": "Weekly", "remaining_fraction": 0.73},
                         {"name": "Five Hour", "remaining_fraction": 0.45}]},
            {"name": "Claude and GPT models", "description": "Claude Opus, Claude Sonnet, GPT-OSS",
             "buckets": [{"name": "Weekly", "remaining_fraction": 0, "reset_time": "2026-10-15T18:34:47Z"},
                         {"name": "Five Hour", "disabled": True, "remaining_fraction": 1}]}]}}}
        check(crew.evaluate_quota(usage, "gemini-3.8-flash-low", 0.05) is None, "gemini quota ok")
        msg = crew.evaluate_quota(usage, "claude-opus-5-5-high", 0.05)
        check(msg and "exhausted" in msg and "2026-10-15" in msg, "claude quota exhausted")
        check(crew.evaluate_quota(usage, "gpt-oss-120b-medium", 0.05), "gpt in the same exhausted group")
        check(crew.evaluate_quota({}, "gemini-x", 0.05), "unreadable usage refuses")
        # agy 1.4.2 (2026-10-18) adds Argon as its own group; on a Pro plan it is a separate quota
        argon = {"name": "Gemini 4 Argon", "description": "For paid Pro plans, Argon quota is separate. Higher "
                 "Argon quota (included as part of the larger Gemini quota bucket) is available on Ultra plans.",
                 "buckets": [{"name": "Gemini 4 Argon Weekly Limit", "remaining_fraction": 0.01,
                              "reset_time": "2026-10-25T01:46:00Z"}]}
        groups = usage["command"]["data"]["groups"]
        groups.append(argon)
        check(crew.evaluate_quota(usage, "gemini-3.8-flash-high", 0.05) is None, "exhausted argon does not block flash")
        msg = crew.evaluate_quota(usage, "gemini-4-argon-medium", 0.05)
        check(msg and "Gemini 4 Argon" in msg, "exhausted argon blocks argon")
        argon["buckets"][0]["remaining_fraction"] = 0.9
        groups[0]["buckets"][0]["remaining_fraction"] = 0
        check(crew.evaluate_quota(usage, "gemini-4-argon-high", 0.05) is None, "exhausted flash does not block argon")
        check(crew.evaluate_quota(usage, "gemini-3.8-flash-low", 0.05), "exhausted flash blocks flash")
        models = crew.parse_models("gemini-3.8-flash-low\tGemini 3.8 Flash (Low)\nFetching available models...\n")
        check(models == ["gemini-3.8-flash-low"], "agy models parsing")

        # install/remove hooks leaves nothing behind and refuses to clobber
        subprocess.run(g + ["checkout", "-q", "--", "."], check=True)
        subprocess.run(g + ["clean", "-q", "-fd"], check=True)

        # what git status cannot see: .git config/hooks/flags, ctx.json, ignored files
        with open(os.path.join(repo, ".gitignore"), "w") as fh:
            fh.write(".env\nbuild/\n")
        subprocess.run(g + ["add", ".gitignore"], check=True)
        subprocess.run(g + ["commit", "-q", "-m", "ignore"], check=True)
        i0, ig0 = crew.integrity_state(repo, rundir), crew.ignored_state(repo)
        os.makedirs(os.path.join(repo, "build"))
        with open(os.path.join(repo, "build", "out.js"), "w") as fh:
            fh.write("x\n")
        check(crew.diff_state(ig0, crew.ignored_state(repo)) == [], "new ignored directory is not noise")
        with open(os.path.join(repo, ".env"), "w") as fh:
            fh.write("X=1\n")
        check(crew.diff_state(ig0, crew.ignored_state(repo)) == [".env"], "ignored .env detected")
        check(crew.changed_paths(repo) == [], "and git status really does not see it")
        subprocess.run(g + ["update-index", "--assume-unchanged", "side.json"], check=True)
        with open(os.path.join(repo, ".git", "config"), "a") as fh:
            fh.write("[core]\n\tfsmonitor = touch FSMON_RAN\n")
        bad = crew.diff_state(i0, crew.integrity_state(repo, rundir))
        crew.changed_paths(repo)
        check(any(b.endswith("config") for b in bad) and "<assume-unchanged/skip-worktree>" in bad,
              f"config and index flag detected: {bad}")
        check(not os.path.exists(os.path.join(repo, "FSMON_RAN")), "planted fsmonitor does not run in the script's git")
        subprocess.run(["git", "-C", repo, "config", "--unset", "core.fsmonitor"], check=True)
        subprocess.run(g + ["update-index", "--no-assume-unchanged", "side.json"], check=True)
        os.remove(os.path.join(repo, ".env"))
        shutil.rmtree(os.path.join(repo, "build"))

        # a timed-out gate command takes its children with it
        t0 = time.time()
        ok, text, _ = crew.run_gate(repo, dict(ctx, gate_timeout=1, gate=dict(ctx["gate"], format=[],
                                          checks=["sleep 30 & sleep 30; wait"])), baseline=True)
        check(not ok and "rc=timeout" in text and time.time() - t0 < 15, "gate timeout")
        created = crew.install_hooks(repo, rundir, ctx)
        spec = crew.read_json(os.path.join(repo, crew.HOOK_FILE))
        check(set(spec["crew"]) == {"SessionStart", "PreToolUse", "Stop"}, "hooks.json generated")
        check(crew.changed_paths(repo) == [], "hooks.json does not count as a change")
        try:
            crew.install_hooks(repo, rundir, ctx)
            check(False, "overwrote existing hooks.json")
        except crew.Refusal as exc:
            check("left over from a crew run" in str(exc) and "rm " in str(exc), "recognizes its own leftover")
        crew.remove_hooks(repo, created)
        check(not os.path.exists(os.path.join(repo, ".agents")), ".agents removed")

        # state: the git dir in a plain checkout. In a linked worktree, laid out as
        # Claude Code desktop does (inside the main checkout), the git path is
        # outside the work tree and Grok's sandbox cannot write it, so state goes
        # to a 0700 dir of this user under STATE_TMP_ROOT (here the test's own).
        real_root, crew.STATE_TMP_ROOT = crew.STATE_TMP_ROOT, os.path.join(tmp, "tmproot")
        os.makedirs(crew.STATE_TMP_ROOT)
        top = os.path.join(crew.STATE_TMP_ROOT, f"crew-state-{os.getuid()}")
        wts = [os.path.join(repo, ".claude", "worktrees", w) for w in ("wt1", "wt2")]
        try:
            check(os.path.realpath(crew.state_base(repo)) == os.path.join(repo, ".git", crew.STATE_NAME)
                  and not os.path.lexists(top), "plain checkout: state in the git dir, nothing in /tmp")
            for w in wts:
                subprocess.run(g + ["worktree", "add", "-q", "-b", os.path.basename(w), w], check=True)
            sb = crew.state_base(wts[0])
            check(os.path.dirname(os.path.dirname(sb)) == top and os.path.basename(sb) == crew.STATE_NAME,
                  f"linked worktree: state under {top}, not in the main checkout's .git: {sb}")
            check(stat.S_IMODE(os.lstat(top).st_mode) == 0o700, "the /tmp state dir is created 0700")
            check(crew.state_base(wts[0]) == sb and crew.state_base(wts[1]) not in (sb, crew.state_base(repo)),
                  "one state dir per worktree, the same on every run")
            wrd = crew.new_rundir(wts[0], "delegate")
            check(os.path.isdir(wrd) and wrd.startswith(sb + os.sep), "the worktree's run dir is in its state")
            wctx = crew.base_ctx(wts[0], task, "delegate")
            check(crew.decide_pre({"toolCall": {"name": "write_to_file", "args": {
                "TargetFile": os.path.join(wrd, "ctx.json"), "CodeContent": "{}"}}}, wctx)["decision"] == "deny"
                  and crew.decide_pre({"toolCall": {"name": "run_command", "args": {
                      "CommandLine": f"cat {wrd}/ctx.json"}}}, wctx)["decision"] == "deny",
                  "the worker may not touch its run dir in /tmp")
            os.chmod(top, 0o775)
            check(crew.state_base(wts[0]) == sb and stat.S_IMODE(os.lstat(top).st_mode) == 0o700,
                  "wider modes on the /tmp state dir (an older crew, a umask) are narrowed to 0700")
            shutil.rmtree(top)
            os.symlink(tmp, top)
            try:
                crew.state_base(wts[0])
                check(False, "a link in place of the /tmp state dir was followed")
            except crew.Refusal as exc:
                check("not a directory of this user" in str(exc), "a link in place of the state dir is refused")
            os.remove(top)
        finally:
            crew.STATE_TMP_ROOT = real_root
            for w in wts:
                subprocess.run(g + ["worktree", "remove", "--force", w], capture_output=True)
                subprocess.run(g + ["branch", "-q", "-D", os.path.basename(w)], capture_output=True)
            shutil.rmtree(os.path.join(repo, ".claude"), ignore_errors=True)
        check(crew.changed_paths(repo) == [], "worktrees removed, the main checkout is clean again")

        # ask: a fake CLI that answers like `agy -p --output-format json`
        import backends
        fakebin = os.path.join(tmp, "fakebin")
        os.makedirs(fakebin)
        fake = os.path.join(fakebin, "agy")
        with open(fake, "w") as fh:
            fh.write("#!/bin/sh\n[ \"$1\" = --version ] && { echo 1.4.4; exit 0; }\n"
                     "case \"$*\" in *--conversation*) id=c1;; *) id=new;; esac\n"
                     "printf '{\"conversation_id\":\"%s\",\"status\":\"SUCCESS\",\"response\":\"pong\"}' $id\n")
        os.chmod(fake, 0o755)
        fenv = dict(os.environ, PATH=fakebin + os.pathsep + os.environ.get("PATH", ""))
        fenv.pop("CLAUDECODE", None)
        old_path = os.environ["PATH"]
        os.environ["PATH"] = fenv["PATH"]
        try:
            v = crew.run_ask("agy", "ping", cwd=repo, env=fenv)
            check(v["ok"] and v["text"] == "pong" and v["session"] == "new"
                  and v["model"] == "gemini-3.8-flash", "ask: first turn")
            v = crew.run_ask("agy", "again", session="c1", cwd=repo, env=fenv)
            check(v["ok"] and v["session"] == "c1", "ask: resumed turn keeps the session")
            with open(fake, "a") as fh:
                fh.write("echo x > touched.txt\n")
            v = crew.run_ask("agy", "ping", cwd=repo, env=fenv)
            check(not v["ok"] and any("work tree changed" in f for f in v["failures"]),
                  "ask: a write during ask fails the verdict")
            os.remove(os.path.join(repo, "touched.txt"))
            try:
                crew.run_ask("claude", "ping", cwd=repo, env=dict(fenv, CLAUDECODE="1"))
                check(False, "ask: claude from claude refused")
            except crew.Refusal:
                check(True, "")
            os.environ[crew.RUN_ENV] = "outer"
            try:
                check(crew.main(["ask", "agy", "ping"]) == 2, "ask: refused inside a crew worker")
            finally:
                del os.environ[crew.RUN_ENV]
            # --web on a backend that keeps its file tools: a new empty directory, not --cwd
            real_root, crew.STATE_TMP_ROOT = crew.STATE_TMP_ROOT, os.path.join(tmp, "webroot")
            os.makedirs(crew.STATE_TMP_ROOT)
            wparent = os.path.join(crew.STATE_TMP_ROOT, f"crew-web-{os.getuid()}")
            runs = os.path.join(crew.state_base(repo), "runs")
            rrepo = os.path.realpath(repo)
            try:
                with open(fake, "w") as fh:      # answers with its directory, what is in it, PWD, OLDPWD, its arguments
                    fh.write("#!/bin/sh\n[ \"$1\" = --version ] && { echo 1.4.4; exit 0; }\n"
                             "printf '{\"conversation_id\":\"w1\",\"status\":\"SUCCESS\",\"response\":\"%s|%s|%s|%s|%s\"}' "
                             "\"$(pwd -P)\" \"$(ls -A | tr '\\n' ,)\" \"$PWD\" \"${OLDPWD:-none}\" \"$*\"\n")
                wenv = dict(fenv, PWD=rrepo, OLDPWD=rrepo)
                v = crew.run_ask("agy", "ping", cwd=repo, env=wenv, web=True)
                d, listing, pwd, oldpwd, args = (v["text"] or "||||").split("|", 4)
                check(v["ok"] and d.startswith(os.path.realpath(wparent) + os.sep) and d.endswith(os.sep + "cwd")
                      and listing == "" and "new empty directory" in v["read_only"],
                      "ask --web: agy runs in a new empty directory under crew-web-<uid>")
                check(os.path.realpath(pwd) == d and oldpwd == "none" and rrepo not in args,
                      "ask --web: PWD, OLDPWD and the arguments do not name the repository")
                check(os.listdir(wparent) == [] and stat.S_IMODE(os.lstat(wparent).st_mode) == 0o700,
                      "ask --web: the run's directory is removed afterwards")
                v = crew.run_ask("agy", "ping", cwd=repo, env=wenv, web=True, schema={"type": "object"})
                check("--json-schema" in (v["text"] or "") and rrepo not in (v["text"] or ""),
                      "ask --web: the schema file handed to the worker is not in the repository's state")
                v = crew.run_ask("agy", "ping", cwd=repo, env=wenv)
                check(v["ok"] and v["text"].split("|")[0] == rrepo and v["text"].split("|")[3] == rrepo
                      and "empty directory" not in v["read_only"], "ask: without --web the worker runs in --cwd")
                stale, fresh = os.path.join(wparent, "stale"), os.path.join(wparent, "fresh")
                for p in (stale, fresh):
                    os.makedirs(os.path.join(p, "cwd"))
                os.utime(stale, (time.time() - 2 * 86400,) * 2)
                with open(fake, "a") as fh:
                    fh.write("echo x > left.txt\n")
                v = crew.run_ask("agy", "ping", cwd=repo, env=wenv, web=True)
                check(not v["ok"] and any("left.txt" in f for f in v["failures"]) and crew.changed_paths(repo) == [],
                      "ask --web: a write in the empty directory fails the run and leaves the repo alone")
                check(os.listdir(wparent) == ["fresh"],
                      "ask --web: a day-old leftover is removed, a fresh neighbour is kept")
                shutil.rmtree(wparent)
                os.symlink(repo, wparent)
                before = sorted(os.listdir(runs))
                try:
                    crew.run_ask("agy", "ping", cwd=repo, env=wenv, web=True)
                    check(False, "ask --web: a link in place of crew-web-<uid> is refused")
                except crew.Refusal as exc:
                    check("crew-web-" in str(exc), "ask --web: a link in place of crew-web-<uid> is refused")
                check(crew.changed_paths(repo) == [] and sorted(os.listdir(runs)) == before,
                      "ask --web: the refusal ran nothing and left no run directory")
                os.unlink(wparent)
            finally:
                crew.STATE_TMP_ROOT = real_root
            # review on an ask backend: no JSON on turn 1, the report on the resumed turn
            fcx = os.path.join(fakebin, "codex")
            with open(fcx, "w") as fh:
                fh.write("#!/bin/sh\n[ \"$1\" = --version ] && { echo codex-cli 0.163.0; exit 0; }\n"
                         "echo '{\"type\":\"thread.started\",\"thread_id\":\"t1\"}'\n"
                         "case \"$*\" in *resume*) txt='{\\\"verdict\\\":\\\"approve\\\",\\\"findings\\\":[],"
                         "\\\"summary\\\":\\\"ok\\\"}';; *) txt='looks fine';; esac\n"
                         "printf '{\"type\":\"item.completed\",\"item\":{\"type\":\"agent_message\","
                         "\"text\":\"%s\"}}\\n' \"$txt\"\n")
            os.chmod(fcx, 0o755)
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(io.StringIO()):
                rc = crew.main(["review", "is add() right?", "--backend", "codex", "--repo", repo])
            rv = json.loads(buf.getvalue())
            check(rc == 0 and rv["turns"] == 2 and rv["report"]["verdict"] == "approve",
                  "review via ask: asks again in the same session for the missing report")
        finally:
            os.environ["PATH"] = old_path
        check(backends.self_test() == 0, "backends self-test")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"self-test: {n} checks ok")
    return 0


if __name__ == "__main__":
    sys.exit(self_test())
