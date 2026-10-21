---
name: music-and-stock
description: Gets music, sound effects, stock photos and stock video under licenses that allow commercial use — ACE-Step 1.5 locally for music, and Openverse, Freesound, Pexels and Pixabay by API — and records the license of each item. Use when a task asks for a soundtrack, background music, "copyright free", royalty-free, b-roll, stock footage, SFX, a whoosh, a stock image library, Creative Commons, CC0, CC-BY, attribution, or when someone plans to use Jamendo, the YouTube Audio Library or "a Pixabay track" in company video.
---

# Music, effects and stock media with commercial licenses

"Copyright free" does not exist; a license that allows your use does. Every
service shows the media for free and hides the condition in its terms.

| Source | Has | License | Trap |
|---|---|---|---|
| ACE-Step 1.5 (local GPU) | generated music, instrumental or vocal | MIT (code and weights) | loads a 1.7B LM even with `thinking=false` and overflows 8 GB; use the toml below |
| Openverse (API, no key) | CC audio and images | per item; `license_type=commercial` filters | the filter trusts declared metadata; check the item's page |
| Freesound (API, key) | SFX | per item; filter `license:"Creative Commons 0"` | original downloads need OAuth2; the HQ mp3 preview does not and is enough for SFX |
| Pexels (API, key) | photos and video | Pexels License: commercial, attribution optional | the CDN returns 403 without a `User-Agent`; pick the widest of the `video_files` |
| Pixabay (API, key) | photos and video | Pixabay Content License: commercial, no standalone resale | no music through the API; terms require caching responses for 24 h |
| Jamendo | music | free API is non-commercial only | institutional video needs a paid license |
| YouTube Audio Library | music | YouTube use only | LinkedIn and Instagram are out |

CC-BY requires credit per item, visible in the piece or its description. Keep
a `CREDITS.json` beside the files with id, author, license and URL; the script
prints exactly those fields.

## Search and download

From this skill's directory (stdlib only; keys from the environment, injected
by your secrets manager's `run`, never a `.env` in the repo):

```bash
python3 scripts/media-search.py openverse "ambient piano" --type audio --download DIR
python3 scripts/media-search.py freesound "whoosh" --license cc0 --download DIR             # FREESOUND_API_KEY
python3 scripts/media-search.py pexels "industrial plant drone" --type video --download DIR  # PEXELS_API_KEY
python3 scripts/media-search.py pixabay "wastewater treatment" --type photo                   # PIXABAY_API_KEY
```

## ACE-Step 1.5 on 8 GB

The diffusion model fits; the auxiliary 1.7B LM the default config loads does
not, and `thinking = false` does not disable it. Use
`references/ace-step-8gb.toml`: every `use_cot_*`, `use_format` and
`sample_mode` false; `offload_to_cpu` and `offload_dit_to_cpu` true.

```bash
cd <ACE-Step-1.5 clone> && uv run python cli.py --config /path/to/ace-step-8gb.toml
```

Install with `uv sync` in the clone (Python 3.11 or 3.12). `save_dir` in the
toml is absolute: point it outside the clone.

A caption that worked for institutional music: "calm ambient, warm analog pad,
soft piano, no drums, minimal, slow evolving", `instrumental = true`, 70 bpm,
8 steps, `guidance_scale` 7. Generate 40 s rather than 60 — the end tends to
degrade — and loop with a 2 s crossfade for the rest.

## In the video

- Music at 0.5 alone, about 0.16 under the voice, ~0.35 s ramp; loudness
  targets are in the `voice-over` skill.
- Download b-roll at 1080p30; re-encoding 4K at render time costs more.
