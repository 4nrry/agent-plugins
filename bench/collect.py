#!/usr/bin/env python3
"""Harvest a workflow transcript directory into a benchmark run record.

Reads the durable per-agent transcripts (agent-*.jsonl + agent-*.meta.json)
under a Claude Code workflow transcript directory and emits one JSON record
conforming to schema/run.schema.json. Collect immediately after a run: the
task-level summary in tmp storage does not survive a restart, and it carries
less than the transcripts do (no cache split, no per-call detail).

Where the transcript directory lives: the Workflow tool result prints it as
"Transcript dir: ..." at launch. Its shape is
  ~/.claude/projects/<project-slug>/subagents/workflows/<workflow_run_id>/
containing one agent-<id>.jsonl + agent-<id>.meta.json pair per agent.

Measurement notes, paid for against real transcripts:
- One API call spans several JSONL assistant lines sharing one message.id,
  whose usage snapshots are PROGRESSIVE (streaming) — summing every line
  double-counts, keeping the first undercounts. This tool keeps the
  field-wise maximum per message.id. api_calls counts unique ids.
- The per-agent model is read from message.model in the transcript (a
  resolved ID like claude-haiku-4-5-20251001), falling back to the alias in
  meta.json only when no assistant message exists.
- totals.wall_duration_ms = (latest timestamp across all agents) - (earliest
  across all agents). It is a lower bound on the pipeline's real wall time
  whenever agents ran outside this workflow (see untracked_agents).

Stdlib only. Task-level fields the transcripts cannot know (question,
variable, arm, phase mapping, outcomes) are supplied by flags or by editing
the emitted record — every measured field is filled by the tool, and the
placeholders it leaves are marked FILL so an unedited record is visibly
incomplete.

Usage:
  collect.py TRANSCRIPT_DIR --run-id 2026-08-06-example-pilot \
      --plugin agent-fleet --plugin-version 1.0.2 \
      --orchestrator-model claude-fable-5 \
      --claude-code-version "$(claude --version)" \
      [--phase-map 'breadth=aeb5,a0db;verify=a79a'] [-o out.json] [--force]

--phase-map assigns phases by agent-id prefix (comma-separated prefixes per
phase, phases separated by ';'). Unmapped agents get phase "unassigned" so a
half-mapped record fails review by inspection, not silently.
"""

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

RUN_ID_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}-[a-z0-9-]+$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def parse_ts(s):
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            return datetime.strptime(s.replace("Z", "+0000"), fmt)
        except ValueError:
            continue
    return None


def first_user_prompt(entries):
    for e in entries:
        if e.get("type") != "user":
            continue
        content = (e.get("message") or {}).get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    return block.get("text", "")
    return ""


def harvest_agent(jsonl_path: Path, meta_path: Path):
    entries = []
    with open(jsonl_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))

    assistant = [e for e in entries if e.get("type") == "assistant"]
    if not assistant:
        sys.exit(f"collect.py: {jsonl_path.name} has no assistant entries — "
                 "crashed or empty agent; record it under untracked_agents by "
                 "hand instead of letting a zero row deflate the totals")
    if not meta_path.exists():
        sys.exit(f"collect.py: {meta_path.name} missing — cannot attribute "
                 "agent_type; refusing to guess")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))

    # Field-wise max usage per message.id (progressive streaming snapshots).
    per_call = {}
    models = set()
    for e in assistant:
        msg = e.get("message") or {}
        usage = msg.get("usage")
        mid = msg.get("id")
        if msg.get("model"):
            models.add(msg["model"])
        if not usage or not mid:
            continue
        acc = per_call.setdefault(mid, {"output": 0, "input_uncached": 0,
                                        "cache_write": 0, "cache_read": 0})
        acc["output"] = max(acc["output"], usage.get("output_tokens", 0) or 0)
        acc["input_uncached"] = max(acc["input_uncached"], usage.get("input_tokens", 0) or 0)
        acc["cache_write"] = max(acc["cache_write"], usage.get("cache_creation_input_tokens", 0) or 0)
        acc["cache_read"] = max(acc["cache_read"], usage.get("cache_read_input_tokens", 0) or 0)

    tokens = {k: sum(c[k] for c in per_call.values())
              for k in ("output", "input_uncached", "cache_write", "cache_read")}

    tool_calls = 0
    seen_tool_ids = set()
    for e in assistant:
        content = (e.get("message") or {}).get("content")
        if isinstance(content, list):
            for b in content:
                if isinstance(b, dict) and b.get("type") == "tool_use":
                    tid = b.get("id")
                    if tid not in seen_tool_ids:
                        seen_tool_ids.add(tid)
                        tool_calls += 1

    timestamps, bad_ts = [], 0
    for e in entries:
        ts = e.get("timestamp")
        if not ts:
            continue
        parsed = parse_ts(ts)
        if parsed is None:
            bad_ts += 1
        else:
            timestamps.append(parsed)
    if bad_ts:
        print(f"collect.py: WARNING {jsonl_path.name}: {bad_ts} unparseable "
              f"timestamp(s) — duration may be wrong", file=sys.stderr)

    prompt = first_user_prompt(entries)
    agent_id = jsonl_path.stem.removeprefix("agent-")
    return {
        "agent_id": agent_id,
        "label": None,
        "phase": "unassigned",
        "model": "/".join(sorted(models)) if models else meta.get("model", "unknown"),
        "agent_type": meta.get("agentType", "unknown"),
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "prompt_head": prompt[:160],
        "tokens": tokens,
        "tool_calls": tool_calls,
        "duration_ms": int((max(timestamps) - min(timestamps)).total_seconds() * 1000)
                       if len(timestamps) >= 2 else 0,
        "api_calls": len(per_call),
    }, timestamps


def apply_phase_map(agents, spec):
    if not spec:
        return
    for part in spec.split(";"):
        phase, _, prefixes = part.partition("=")
        phase = phase.strip()
        for prefix in [p.strip() for p in prefixes.split(",") if p.strip()]:
            matches = agents if prefix == "*" else \
                [a for a in agents if a["agent_id"].startswith(prefix)]
            if not matches:
                sys.exit(f"collect.py: phase-map prefix '{prefix}' matches no agent")
            for a in matches:
                a["phase"] = phase


def structural_check(record, schema_path: Path):
    """Structural check: top-level and known nested required keys, plus the
    two regex patterns operators type by hand. NOT full JSON Schema
    validation — review the record before committing it."""
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    problems = []
    required = set(schema["required"])
    allowed = set(schema["properties"].keys())
    keys = set(record.keys())
    if required - keys:
        problems.append(f"missing top-level {sorted(required - keys)}")
    if keys - allowed:
        problems.append(f"extra top-level {sorted(keys - allowed)}")
    if not RUN_ID_RE.match(record.get("run_id", "")):
        problems.append(f"run_id '{record.get('run_id')}' fails pattern {RUN_ID_RE.pattern}")
    agent_req = {"agent_id", "phase", "model", "agent_type", "prompt_sha256",
                 "prompt_head", "tokens", "tool_calls", "duration_ms", "api_calls"}
    token_req = {"output", "input_uncached", "cache_write", "cache_read"}
    for a in record.get("agents", []):
        if agent_req - set(a):
            problems.append(f"agent {a.get('agent_id')} missing {sorted(agent_req - set(a))}")
        if token_req - set(a.get("tokens", {})):
            problems.append(f"agent {a.get('agent_id')} tokens missing fields")
        if not SHA256_RE.match(a.get("prompt_sha256", "")):
            problems.append(f"agent {a.get('agent_id')} prompt_sha256 not a sha256")
    if token_req - set(record.get("totals", {})):
        problems.append("totals missing token fields")
    if problems:
        sys.exit("collect.py: record fails structural check — " + "; ".join(problems))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("transcript_dir", type=Path)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--plugin", required=True)
    ap.add_argument("--plugin-version", required=True)
    ap.add_argument("--orchestrator-model", required=True)
    ap.add_argument("--claude-code-version", required=True,
                    help="output of `claude --version` for the session that ran the workflow")
    ap.add_argument("--question", default="FILL: what this run helps answer")
    ap.add_argument("--variable", default="none")
    ap.add_argument("--arm", default="pilot")
    ap.add_argument("--eval-ref", default=None)
    ap.add_argument("--eval-sha256", default=None,
                    help="sha256 of the frozen eval file (required when --eval-ref is set)")
    ap.add_argument("--batch-id", default=None,
                    help="shared id linking the paired runs of one comparison")
    ap.add_argument("--workflow-run-id", default=None,
                    help="explicit workflow run id; overrides path scraping")
    ap.add_argument("--phase-map", default=None)
    ap.add_argument("-o", "--out", type=Path)
    ap.add_argument("--force", action="store_true",
                    help="allow overwriting an existing output file")
    args = ap.parse_args()

    if args.eval_ref and not args.eval_sha256:
        sys.exit("collect.py: --eval-ref requires --eval-sha256 (freeze means hash)")

    d = args.transcript_dir
    jsonls = sorted(d.glob("agent-*.jsonl"))
    if not jsonls:
        sys.exit(f"collect.py: no agent-*.jsonl under {d}")

    agents, all_ts = [], []
    for p in jsonls:
        agent, ts = harvest_agent(p, d / (p.stem + ".meta.json"))
        agents.append(agent)
        all_ts.extend(ts)
    apply_phase_map(agents, args.phase_map)

    wf_run_id = args.workflow_run_id
    if wf_run_id is None:
        m = re.search(r"(wf_[A-Za-z0-9_-]+)", str(d))
        wf_run_id = m.group(1) if m else None
        if wf_run_id:
            print(f"collect.py: workflow_run_id '{wf_run_id}' scraped from path; "
                  "pass --workflow-run-id to be sure", file=sys.stderr)

    totals = {k: sum(a["tokens"][k] for a in agents)
              for k in ("output", "input_uncached", "cache_write", "cache_read")}
    totals["tool_calls"] = sum(a["tool_calls"] for a in agents)
    totals["wall_duration_ms"] = int((max(all_ts) - min(all_ts)).total_seconds() * 1000) \
        if len(all_ts) >= 2 else 0

    record = {
        "run_id": args.run_id,
        "date": datetime.now(timezone.utc).isoformat(),
        "plugin": args.plugin,
        "plugin_version": args.plugin_version,
        "question": args.question,
        "variable": args.variable,
        "arm": args.arm,
        "batch_id": args.batch_id,
        "eval_ref": args.eval_ref,
        "eval_sha256": args.eval_sha256,
        "harness": {
            "orchestrator_model": args.orchestrator_model,
            "claude_code_version": args.claude_code_version,
            "workflow_run_id": wf_run_id,
            "session_effort": None,
        },
        "agents": agents,
        "untracked_agents": [],
        "totals": totals,
        "outcomes": None,
        "notes": "FILL: provenance — anything estimated or inferred, deviations from protocol.",
    }

    structural_check(record, Path(__file__).parent / "schema" / "run.schema.json")
    out = json.dumps(record, indent=2, ensure_ascii=False)
    if args.out:
        if args.out.exists() and not args.force:
            sys.exit(f"collect.py: {args.out} exists — pass --force to overwrite")
        args.out.write_text(out + "\n", encoding="utf-8")
        print(f"wrote {args.out}", file=sys.stderr)
    else:
        print(out)


if __name__ == "__main__":
    main()
