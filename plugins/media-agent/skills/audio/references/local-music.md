# Music on your own GPU: ACE-Step 1.5

MIT license (code and weights). On 8 GB the diffusion model fits, but the
auxiliary 1.7B LM that the default config loads does not, and `thinking =
false` does not disable it. Use [ace-step-8gb.toml](ace-step-8gb.toml): every
`use_cot_*`, `use_format` and `sample_mode` false; `offload_to_cpu` and
`offload_dit_to_cpu` true. Its `save_dir` is absolute: point it outside the
clone.

```bash
cd <ACE-Step-1.5 clone> && uv sync          # Python 3.11 or 3.12
uv run python cli.py --config /path/to/ace-step-8gb.toml
```

A caption that worked for institutional music: "calm ambient, warm analog pad,
soft piano, no drums, minimal, slow evolving", `instrumental = true`, 70 bpm,
8 steps, `guidance_scale` 7, 40 s.
