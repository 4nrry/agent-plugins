# Cross-cutting benchmark records

`bench/plugins/<name>/` holds work measured on one plugin. This directory is for
records whose finding does not belong to any single plugin — a fact about model
routing, harness behaviour, or measurement method that a second plugin would
reuse rather than re-derive.

Nothing lives here yet. `2026-08-07-breadth-tier` is the closest candidate: it
measures which model tier to use for a breadth fan-out, which is a fact about
orchestration rather than about `agent-fleet`. It stays under `agent-fleet`
because that is what it was measured on; move it here the day a second plugin
cites it, and say so in its claims file.
