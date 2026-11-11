#!/usr/bin/env python3
"""Fixture test for plugins/agent-fleet/hooks/inject.sh.

  check_inject_hook.py --self-test

Pipes sample UserPromptSubmit JSON into the hook and checks what it prints:
the whole SKILL.md on the first matching prompt of a session, a short pointer
on the next ones, the whole text again after `--forget`, and the whole text
every time when there is no usable session id, no writable data directory, or
no CLAUDE_PLUGIN_DATA (the bridges for other harnesses, which send no
SessionStart). A prompt that does not match prints nothing and leaves no
marker. Which prompts match is scored elsewhere
(results/2026-10-26-pesquisa-trigger/).
The hook takes the plugin folder from `--root` or CLAUDE_PLUGIN_ROOT; with
neither a matching prompt gets an error line and no text. Needs bash and jq; without jq
it reports a skip, since the hook then does nothing.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4] / "plugins/agent-fleet"
HOOK = ROOT / "hooks/inject.sh"
BODY = (ROOT / "skills/agent-fleet/SKILL.md").read_text(encoding="utf-8")
MATCH = "run a deep research on battery chemistry"
MISS = "rename this variable"


def run(payload, data_dir, *args, home=None):
    stdin = payload if isinstance(payload, str) else json.dumps(payload)
    env = {k: v for k, v in os.environ.items() if k not in ("CLAUDE_PLUGIN_DATA", "HOME")}
    env["CLAUDE_PLUGIN_ROOT"] = str(ROOT)
    if data_dir is not None:
        env["CLAUDE_PLUGIN_DATA"] = data_dir
    if home is not None:
        env["HOME"] = home
    elif data_dir is not None:
        env["HOME"] = os.environ.get("HOME", "")
    p = subprocess.run(["bash", str(HOOK), *args], input=stdin, capture_output=True, text=True, timeout=30,
                       env=env)
    kind = "none" if not p.stdout else "full" if BODY in p.stdout else "pointer"
    if kind == "pointer" and ("injected earlier" not in p.stdout or len(p.stdout) > 1000):
        kind = "unexpected output"
    return p.returncode, kind


def self_test():
    if not shutil.which("jq"):
        print("self-test skipped: jq not installed, and without it the hook does nothing")
        return 0
    fails = []

    def expect(label, got, want):
        if got != want:
            fails.append(f"{label}: got {got!r}, expected {want!r}")

    with tempfile.TemporaryDirectory() as tmp:
        data = str(Path(tmp, "data"))
        markers = Path(data, "injected")
        prompt = lambda sid, text=MATCH: {"session_id": sid, "prompt": text}  # noqa: E731

        expect("a prompt that does not match", run(prompt("s1", MISS), data), (0, "none"))
        expect("no marker after a miss", markers.exists() and any(markers.iterdir()), False)
        expect("first match in a session", run(prompt("s1"), data), (0, "full"))
        expect("marker written", (markers / "s1").is_file(), True)
        expect("second match in the session", run(prompt("s1"), data), (0, "pointer"))
        expect("third match in the session", run(prompt("s1"), data), (0, "pointer"))
        expect("first match in another session", run(prompt("s2"), data), (0, "full"))
        expect("--forget prints nothing", run({"session_id": "s1", "source": "compact"}, data, "--forget"),
               (0, "none"))
        expect("marker removed by --forget", (markers / "s1").exists(), False)
        expect("the other session's marker stays", (markers / "s2").is_file(), True)
        expect("first match after --forget", run(prompt("s1"), data), (0, "full"))
        expect("--forget for a session never seen", run({"session_id": "s9"}, data, "--forget"), (0, "none"))
        expect("--forget with input that is not JSON", run("not json", data, "--forget"), (0, "none"))

        no_sid = {"prompt": MATCH}
        expect("no session id, first", run(no_sid, data), (0, "full"))
        expect("no session id, second", run(no_sid, data), (0, "full"))
        before = sorted(p.name for p in Path(tmp).rglob("*"))
        expect("a session id that is a path, first", run(prompt("../../escape"), data), (0, "full"))
        expect("a session id that is a path, second", run(prompt("../../escape"), data), (0, "full"))
        expect("no file written for it", sorted(p.name for p in Path(tmp).rglob("*")), before)

        blocked = Path(tmp, "a-file")
        blocked.write_text("x", encoding="utf-8")
        bad = str(blocked / "data")
        expect("data directory cannot be created, first", run(prompt("s3"), bad), (0, "full"))
        expect("data directory cannot be created, second", run(prompt("s3"), bad), (0, "full"))

        # No CLAUDE_PLUGIN_DATA: a bridge for another harness. With and without HOME.
        home = Path(tmp, "home")
        home.mkdir()
        expect("no data variable, first", run(prompt("s5"), None, home=str(home)), (0, "full"))
        expect("no data variable, second", run(prompt("s5"), None, home=str(home)), (0, "full"))
        expect("nothing written under HOME", any(home.iterdir()), False)
        expect("no data variable and no HOME", run(prompt("s5"), None), (0, "full"))
        expect("--forget with no data variable and no HOME", run({"session_id": "s5"}, None, "--forget"),
               (0, "none"))

        ro = Path(tmp, "ro", "injected")
        ro.mkdir(parents=True)
        ro.chmod(0o500)
        p = subprocess.run(["bash", str(HOOK)], input=json.dumps(prompt("s6")), capture_output=True, text=True,
                           timeout=30, env={**os.environ, "CLAUDE_PLUGIN_DATA": str(ro.parent),
                                            "CLAUDE_PLUGIN_ROOT": str(ROOT)})
        ro.chmod(0o700)
        if os.geteuid() != 0:
            expect("marker directory not writable", (p.returncode, BODY in p.stdout, p.stderr), (0, True, ""))

        # The plugin folder comes from CLAUDE_PLUGIN_ROOT and from nowhere else.
        bare = {k: v for k, v in os.environ.items() if k != "CLAUDE_PLUGIN_ROOT"}
        rel = os.path.relpath(ROOT, tmp)
        for label, text, env, args, want in [
                ("no plugin folder, a matching prompt", MATCH, bare, [], (1, "", True)),
                ("no plugin folder, a prompt that does not match", MISS, bare, [], (0, "", False)),
                ("no plugin folder, --forget", MATCH, bare, ["--forget"], (0, "", False)),
                ("an empty --root and no variable", MATCH, bare, ["--root", ""], (1, "", True)),
                ("--root alone, as a harness that only fills the command gives it", MATCH, bare,
                 ["--root", str(ROOT)], (0, "full", False)),
                ("--root wins over the variable", MATCH, {**bare, "CLAUDE_PLUGIN_ROOT": tmp},
                 ["--root", str(ROOT)], (0, "full", False)),
                ("a plugin folder with no skill in it", MATCH, {**bare, "CLAUDE_PLUGIN_ROOT": tmp}, [], (1, "", True)),
                ("a plugin folder with a trailing slash", MATCH,
                 {**bare, "CLAUDE_PLUGIN_ROOT": str(ROOT) + "/"}, [], (0, "full", False)),
                ("a relative plugin folder is printed as an absolute path", MATCH, bare, ["--root", rel],
                 (0, "full", False))]:
            p = subprocess.run(["bash", str(HOOK), *args], input=json.dumps({"prompt": text}), capture_output=True,
                               text=True, timeout=30, env=env, cwd=tmp)
            out = "full" if BODY in p.stdout else p.stdout
            if out == "full" and "Skill directory: /" not in p.stdout:
                out = "relative skill directory"
            expect(label, (p.returncode, out, bool(p.stderr.strip())), want)

        # 60,000 filler lines after the trigger: a pipe into grep -q under
        # pipefail read this as "no match" before 1.9.2.
        long_prompt = MATCH + "\n" + "filler line\n" * 60000
        expect("trigger at the top of a long prompt", run(prompt("s4", long_prompt), data), (0, "full"))
        expect("input that is not JSON", run("not json", data), (0, "none"))
    for f in fails:
        print("FAIL:", f)
    print(f"self-test: {'ok' if not fails else str(len(fails)) + ' failed'}")
    return 1 if fails else 0


if __name__ == "__main__":
    if "--self-test" not in sys.argv[1:]:
        sys.exit(__doc__)
    sys.exit(self_test())
