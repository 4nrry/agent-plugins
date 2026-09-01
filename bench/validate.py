#!/usr/bin/env python3
"""Mechanical checks over the whole repository — every convention this repo
relies on that a human would otherwise have to hold in their head.

Run it as `just check`. It is the guardrail for a marketplace holding more than
one plugin: the conventions below are what let a second plugin land without
touching the first, and none of them survives on discipline alone.

What it refuses to do: pass quietly. The run-record validator raises on any
JSON Schema keyword it does not implement, rather than skipping it — a
hand-rolled validator that ignores what it does not understand reports success
it did not verify, which is worse than having no validator at all.

No third-party dependencies: stdlib only, so CI needs nothing installed and a
clone can run it immediately. shellcheck and the per-script self-tests are used
when present and reported as skipped when not.
"""

import hashlib
import json
import pathlib
import re
import shutil
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
SELF_TEST_TIMEOUT = 120

failures: list[str] = []
warnings: list[str] = []
checks_run = 0


def fail(where: str, msg: str) -> None:
    failures.append(f"{where}: {msg}")


def warn(where: str, msg: str) -> None:
    warnings.append(f"{where}: {msg}")


def rel(p: pathlib.Path) -> str:
    try:
        return str(p.relative_to(REPO))
    except ValueError:
        return str(p)


def load_json(p: pathlib.Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 — any parse problem is a failure
        fail(rel(p), f"does not parse as JSON: {exc}")
        return None


def sha256(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


# --------------------------------------------------------------------------
# A minimal JSON Schema validator, deliberately partial and loudly so.
# --------------------------------------------------------------------------

HANDLED = {"$schema", "title", "description", "type", "required", "properties",
           "additionalProperties", "pattern", "minimum", "maximum", "maxLength",
           "minLength", "items", "enum", "format"}

TYPES = {"object": dict, "array": list, "string": str, "boolean": bool,
         "null": type(None)}


def check_schema(value, schema: dict, path: str, errs: list[str]) -> None:
    unhandled = set(schema) - HANDLED
    if unhandled:
        raise NotImplementedError(
            f"run.schema.json uses JSON Schema keyword(s) {sorted(unhandled)} at "
            f"{path or '<root>'}, which validate.py does not implement. Implement "
            f"them or this check is silently weaker than it looks.")

    types = schema.get("type")
    if types is not None:
        types = [types] if isinstance(types, str) else types
        ok = False
        for t in types:
            if t == "integer":
                ok = ok or (isinstance(value, int) and not isinstance(value, bool))
            elif t == "number":
                ok = ok or (isinstance(value, (int, float)) and not isinstance(value, bool))
            else:
                ok = ok or isinstance(value, TYPES[t])
        if not ok:
            errs.append(f"{path or '<root>'}: expected type {types}, got {type(value).__name__}")
            return

    if "enum" in schema and value not in schema["enum"]:
        errs.append(f"{path}: {value!r} not in {schema['enum']}")

    if isinstance(value, str):
        if "pattern" in schema and not re.search(schema["pattern"], value):
            errs.append(f"{path}: {value!r} does not match /{schema['pattern']}/")
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            errs.append(f"{path}: longer than maxLength {schema['maxLength']}")
        if "minLength" in schema and len(value) < schema["minLength"]:
            errs.append(f"{path}: shorter than minLength {schema['minLength']}")

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errs.append(f"{path}: {value} below minimum {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            errs.append(f"{path}: {value} above maximum {schema['maximum']}")

    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                errs.append(f"{path or '<root>'}: missing required field {key!r}")
        props = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            for key in value:
                if key not in props:
                    errs.append(f"{path or '<root>'}: undeclared field {key!r}")
        for key, sub in props.items():
            if key in value:
                check_schema(value[key], sub, f"{path}.{key}" if path else key, errs)

    if isinstance(value, list) and "items" in schema:
        for i, item in enumerate(value):
            check_schema(item, schema["items"], f"{path}[{i}]", errs)


# --------------------------------------------------------------------------
# Checks
# --------------------------------------------------------------------------

def check_marketplace(plugin_dirs: dict) -> None:
    """1. Entries carry only name+source, and source resolves to a real plugin.

    The docs make version/description/author optional in a marketplace entry,
    and in strict mode (the default) plugin.json is the authority and the two
    are merged. Duplicating them here buys nothing and drifts silently — this
    repo shipped a version bump that had to be applied by hand in two files.
    """
    global checks_run
    mp = REPO / ".claude-plugin" / "marketplace.json"
    if not mp.is_file():
        return fail(".claude-plugin/marketplace.json", "missing")
    d = load_json(mp)
    if d is None:
        return
    for entry in d.get("plugins", []):
        checks_run += 1
        name = entry.get("name", "<unnamed>")
        extra = sorted(set(entry) - {"name", "source"})
        if extra:
            fail(f"marketplace.json[{name}]",
                 f"carries {extra}, which plugin.json already owns — the entry "
                 f"needs only name and source")
        src = entry.get("source")
        if not isinstance(src, str):
            fail(f"marketplace.json[{name}]", "source is not a path string")
            continue
        target = (REPO / src.lstrip("./")).resolve()
        if not (target / ".claude-plugin" / "plugin.json").is_file():
            fail(f"marketplace.json[{name}]",
                 f"source {src!r} has no .claude-plugin/plugin.json")
        elif name not in plugin_dirs:
            fail(f"marketplace.json[{name}]", "names no plugin directory")


def check_plugins() -> dict:
    """2. plugin.json parses, is named after its directory, and has a version.
    7. Any bench/ path cited in its description exists."""
    global checks_run
    found = {}
    for manifest in sorted((REPO / "plugins").glob("*/.claude-plugin/plugin.json")):
        checks_run += 1
        plugin_dir = manifest.parent.parent
        d = load_json(manifest)
        if d is None:
            continue
        name = d.get("name")
        if name != plugin_dir.name:
            fail(rel(manifest), f"name {name!r} != directory {plugin_dir.name!r}")
        if not d.get("version"):
            fail(rel(manifest), "no version")
        found[name] = plugin_dir

        for cited in re.findall(r"bench/[A-Za-z0-9._/-]+", d.get("description", "")):
            checks_run += 1
            if not (REPO / cited.rstrip(".,);")).exists():
                fail(rel(manifest), f"description cites {cited}, which does not exist")
    if not found:
        fail("plugins/", "no plugin manifests found")
    return found


def check_hooks(plugin_dirs: dict) -> None:
    """3. Every hook command points at a file that exists."""
    global checks_run
    for plugin_dir in plugin_dirs.values():
        for hooks_file in sorted(plugin_dir.rglob("hooks.json")):
            d = load_json(hooks_file)
            if d is None:
                continue
            for event, groups in d.get("hooks", {}).items():
                for group in groups:
                    for hook in group.get("hooks", []):
                        checks_run += 1
                        cmd = hook.get("command", "")
                        m = re.search(r'\$\{CLAUDE_PLUGIN_ROOT\}"?(/[^\s"]+)', cmd)
                        if not m:
                            warn(rel(hooks_file),
                                 f"{event} command not resolvable to a path: {cmd!r}")
                            continue
                        target = plugin_dir / m.group(1).lstrip("/")
                        if not target.is_file():
                            fail(rel(hooks_file), f"{event} points at missing {rel(target)}")
                        elif not target.stat().st_mode & 0o111:
                            fail(rel(hooks_file), f"{event} target {rel(target)} is not executable")


def check_records(plugin_dirs: dict) -> None:
    """4. Records conform to run.schema.json.
    5. eval_ref resolves and the file hashes to eval_sha256.
    6. The record's plugin exists."""
    global checks_run
    schema = load_json(REPO / "bench" / "schema" / "run.schema.json")
    if schema is None:
        return
    records = sorted((REPO / "bench").glob("plugins/*/results/**/*.json"))
    records = [r for r in records if not r.name.startswith("results")
               and "logs" not in r.parts]
    if not records:
        warn("bench/", "no run records found to validate")
    for rec_path in records:
        checks_run += 1
        rec = load_json(rec_path)
        if rec is None:
            continue
        # Imported records are published raw and do not conform; their claims
        # file says so. They live in a directory, not as a flat run file.
        errs: list[str] = []
        check_schema(rec, schema, "", errs)
        for e in errs:
            fail(rel(rec_path), e)

        if rec.get("plugin") and rec["plugin"] not in plugin_dirs:
            fail(rel(rec_path), f"plugin {rec['plugin']!r} has no directory under plugins/")

        ref, want = rec.get("eval_ref"), rec.get("eval_sha256")
        if ref:
            checks_run += 1
            target = REPO / ref
            if not target.is_file():
                fail(rel(rec_path), f"eval_ref {ref} does not resolve")
            elif want and sha256(target) != want:
                fail(rel(rec_path),
                     f"eval_sha256 {want[:12]}… does not match {ref} "
                     f"(actual {sha256(target)[:12]}…) — the eval was edited, or "
                     f"eval_ref points at the wrong file")
        elif want:
            fail(rel(rec_path), "eval_sha256 set but eval_ref is null")


def check_claims_hashes() -> None:
    """Truncated hashes cited in claims files should match something on disk.

    Warning, not failure: a claims file may legitimately cite an artefact that
    is not committed. A miss is worth a human look, not a red build.
    """
    global checks_run
    on_disk = {}
    for p in REPO.rglob("*"):
        # Whole repo, not just bench/: claims files cite the hash of the thing
        # under test, and for a hook that lives under plugins/.
        if p.is_file() and ".git" not in p.parts:
            on_disk[sha256(p)] = rel(p)
    for claims in sorted((REPO / "bench").rglob("*CLAIMS.md")):
        text = claims.read_text(encoding="utf-8")
        seen = set()
        for m in re.finditer(r"`?([0-9a-f]{8,12})[…]([0-9a-f]{4})`?", text):
            head, tail = m.groups()
            if (head, tail) in seen:
                continue
            seen.add((head, tail))
            checks_run += 1
            if any(h.startswith(head) and h.endswith(tail) for h in on_disk):
                continue
            # A claims file may cite an artefact deliberately no longer on disk —
            # the version of a script a batch was measured against, before a
            # later edit. Marking it "historical" within the next 120 characters
            # is the opt-out, and it is checked rather than assumed: the marker
            # has to be there.
            if "historical" in text[m.end():m.end() + 120].lower():
                continue
            warn(rel(claims), f"cites {head}…{tail}, which matches no file in the repo")


def check_shell() -> None:
    """8. shellcheck over every tracked shell script, at `style`.

    Not `warning`: SC2006 — backticks where $() belongs — is severity `style`,
    and a `warning` gate let through an unescaped backtick inside a
    double-quoted string. It reached a shipped script, where the shell ran it:
    the help text for an empty accessibility tree invoked `android`, which is a
    bootstrapper that downloads hundreds of MB. A gate that misses the class of
    bug the repo exists to document is the wrong gate.

    Intentional cases opt out in the file, with a reason, via
    `# shellcheck disable=<code>`.
    """
    global checks_run
    scripts = sorted(REPO.rglob("*.sh"))
    scripts = [s for s in scripts if ".git" not in s.parts]
    if not shutil.which("shellcheck"):
        return warn("shellcheck", f"not installed — {len(scripts)} script(s) unchecked")
    for s in scripts:
        checks_run += 1
        proc = subprocess.run(["shellcheck", "-S", "style", str(s)],
                              capture_output=True, text=True)
        if proc.returncode != 0:
            fail(rel(s), "shellcheck:\n" + proc.stdout.strip())


def check_self_tests() -> None:
    """9. Any script advertising --self-test must pass it.

    Opt-in by convention: a script joins this check by supporting the flag.
    That is what caught the bench/ move — score_hook_grep.py resolved the repo
    root by counting directory levels, and namespacing bench/ by plugin moved
    it two levels deeper.
    """
    global checks_run
    for script in sorted(REPO.rglob("*.py")):
        if ".git" in script.parts or script.name == "validate.py":
            continue
        if "--self-test" not in script.read_text(encoding="utf-8"):
            continue
        checks_run += 1
        try:
            proc = subprocess.run([sys.executable, str(script), "--self-test"],
                                  capture_output=True, text=True,
                                  timeout=SELF_TEST_TIMEOUT, cwd=REPO)
        except subprocess.TimeoutExpired:
            fail(rel(script), f"--self-test exceeded {SELF_TEST_TIMEOUT}s")
            continue
        if proc.returncode != 0:
            fail(rel(script), "--self-test failed:\n"
                 + (proc.stdout + proc.stderr).strip()[:2000])


def main() -> int:
    plugin_dirs = check_plugins()
    check_marketplace(plugin_dirs)
    check_hooks(plugin_dirs)
    check_records(plugin_dirs)
    check_claims_hashes()
    check_shell()
    check_self_tests()

    for w in warnings:
        print(f"warn  {w}")
    for f in failures:
        print(f"FAIL  {f}")

    print(f"\n{checks_run} checks, {len(failures)} failed, {len(warnings)} warning(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
