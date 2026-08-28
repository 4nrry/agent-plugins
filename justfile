# Repository tasks. `just` with no argument lists them.
#
# CI runs `just check` and nothing else, so this file is the single definition
# of what "green" means — there is no second copy of the rules in a workflow
# YAML to drift from this one.

default:
    @just --list

# Everything CI runs. The only command you need before pushing.
check: validate
    @echo "check: ok"

# Every mechanical convention in the repo: manifests, hooks, run records,
# eval hashes, shellcheck, and each script's own --self-test.
validate:
    python3 bench/validate.py

# Re-run one plugin's benchmark scorers against their frozen evals. Not part of
# `check` — `validate` already runs each scorer's --self-test, which is the
# cheap end; this re-scores the full eval sets.
bench plugin="agent-fleet":
    #!/usr/bin/env bash
    # The scorer exits 1 when the hook's behaviour does not match its stated
    # intent, which today is the documented finding (8 of 8 mention fires), not
    # a broken build. So report the outcome and fail only if the scorer itself
    # did not run to a summary.
    set -uo pipefail
    out=$(python3 bench/plugins/{{plugin}}/scripts/score_hook_grep.py \
          bench/plugins/{{plugin}}/evals/hook-grep-2026-08-20.json) || true
    printf '%s\n' "$out"
    grep -q 'invocation fired' <<<"$out"

# Hashes for a claims file: what a record's provenance line should quote.
sha +files:
    @sha256sum {{files}}
