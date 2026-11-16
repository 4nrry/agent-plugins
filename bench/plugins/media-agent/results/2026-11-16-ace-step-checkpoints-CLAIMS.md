# Batch 2026-11-16-ace-step-checkpoints — claims

**Notes, not run records.** Why media-agent 0.25.1 tells the audio skill to
set `ACESTEP_CHECKPOINTS_DIR` on every ACE-Step run. Read and measured on
2026-11-16 against an ACE-Step 1.5 clone at commit `ca1e85f` with its own
`uv sync` environment (Python 3.12), Linux, one machine. Nothing here
compares an agent with and without the skill.

**The failure.** An agent following `references/local-music.md` ran ACE-Step
through a launcher on PATH (the clone's Python and `cli.py`, nothing else)
from its session's temporary folder. ACE-Step found no weights there and
downloaded them into `checkpoints/` of that folder, about 9.5 GB, while the
clone already held the same weights. On that machine `/tmp` is a tmpfs
capped at 16 GB, so the download filled it, and writes to `/tmp` by other
programs failed until those files were removed.

**Why it happens.** `acestep/model_downloader.py` resolves the weights
folder as: an explicit argument, else `ACESTEP_CHECKPOINTS_DIR`, else
`get_project_root() / "checkpoints"`, where `get_project_root()` is
`ACESTEP_PROJECT_ROOT` or, when that is unset, the current working
directory. `cli.py` downloads the main model into that folder when it finds
no `acestep-v15-*` model there. The generation handler's own lookup
(`_resolve_checkpoint_dir`) also honours `ACESTEP_CHECKPOINTS_DIR`.

**Measured.**

- `get_checkpoints_dir()` called with the clone's Python from an empty
  folder outside the clone: that folder's `checkpoints/` without the
  variable; the clone's `checkpoints/` with
  `ACESTEP_CHECKPOINTS_DIR=<clone>/checkpoints`.
- The same, through a launcher that sets the variable when unset: the
  clone's `checkpoints/`. `--help` through it from an empty folder exited 0
  and left the folder empty.
- The clone's `checkpoints/` holds 10.09 GB: `acestep-v15-turbo` 4.79,
  `acestep-5Hz-lm-1.7B` 3.76, `Qwen3-Embedding-0.6B` 1.21, `vae` 0.34. The
  skill says "about 10 GB".

**Not measured.** A full generation through a launcher with the variable set
(the resolution above is what decides the folder; no music was rendered for
this change), the Gradio UI and the REST API (their code calls the same
`get_project_root()`), and other ACE-Step commits.
