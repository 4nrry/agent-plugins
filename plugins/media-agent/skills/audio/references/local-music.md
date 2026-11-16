# Music on your own GPU: ACE-Step 1.5

MIT license (code and weights). On 8 GB the diffusion model fits, but the
auxiliary 1.7B LM that the default config loads does not, and `thinking =
false` does not disable it. Use [ace-step-8gb.toml](ace-step-8gb.toml): every
`use_cot_*`, `use_format` and `sample_mode` false; `offload_to_cpu` and
`offload_dit_to_cpu` true. Its `save_dir` is absolute: point it outside the
clone.

The weights (about 10 GB) are looked for in `checkpoints/` of the folder
ACE-Step runs from, not of the clone, and downloaded there when missing. Set
`ACESTEP_CHECKPOINTS_DIR` to the clone's `checkpoints/` for every run, so a
run from a project folder, a temporary folder or a session scratchpad uses the
weights already downloaded. Where `/tmp` is in RAM, that download alone can
fill it.

```bash
cd <ACE-Step-1.5 clone> && uv sync          # Python 3.11 or 3.12
export ACESTEP_CHECKPOINTS_DIR="$PWD/checkpoints"
uv run python cli.py --config /path/to/ace-step-8gb.toml
```

The README's quick start launches a Gradio UI (`uv run acestep`) or a REST
API (`uv run acestep-api`); `cli.py` is the headless route from a config file.
A machine can wrap it in a launcher on PATH that runs `cli.py` with the
clone's environment and sets `ACESTEP_CHECKPOINTS_DIR` (`ace-step --config
...`); the arguments are the same. Read a launcher before the first run: one
that does not set the variable downloads the weights into the current folder.

A caption that worked for institutional music: "calm ambient, warm analog pad,
soft piano, no drums, minimal, slow evolving", `instrumental = true`, 70 bpm,
8 steps, `guidance_scale` 7, 40 s.
