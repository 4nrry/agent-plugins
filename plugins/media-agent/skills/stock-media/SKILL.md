---
name: stock-media
description: Finds ready-made footage, photos, music and sound effects in stock libraries, under licenses that allow commercial use, with the credit each item needs — which library has what, the trap in each license, and a search-and-download script. Use for stock footage or b-roll, stock photos, royalty-free or CC0 music or sound effects from a library, CC-BY credits or a CREDITS.json, or a named library (Pexels, Pixabay, Openverse, Freesound, Jamendo, YouTube Audio Library). Generated music and effects are in the audio skill; generated shots in video-generation.
---

# Stock media

## Licenses

- "Copyright free" does not exist; a license that allows your use does. Every
  service shows the media for free and keeps the condition in its terms: check
  commercial use, the platforms allowed, and credit.
- CC-BY needs credit per item, visible in the piece or its description. Keep a
  `CREDITS.json` beside the files with id, author, license and URL.
- A license filter in a search API trusts what uploaders declared: open the
  item's page before using it.

## Search and download

`scripts/media-search.py` searches and downloads, and prints the id, author,
license and URL each item needs in `CREDITS.json`. Stdlib only; keys come from
the environment, injected by your secrets manager's `run`, never from a
`.env` in the repo. From the skill's directory:

```bash
python3 scripts/media-search.py openverse "ambient piano" --type audio --download DIR
python3 scripts/media-search.py freesound "whoosh" --license cc0 --download DIR             # FREESOUND_API_KEY
python3 scripts/media-search.py pexels "industrial plant drone" --type video --download DIR  # PEXELS_API_KEY
python3 scripts/media-search.py pixabay "wastewater treatment" --type photo                   # PIXABAY_API_KEY
```

Download footage at 1080p30: re-encoding 4K at render time costs more.

## Which library

[references/libraries.md](references/libraries.md) has each source's license,
the date it was checked and the trap in it. In short:

- Footage and photos: Pexels, Pixabay.
- Sound effects: Freesound, filtered to CC0.
- CC audio and images: Openverse, no key needed.
- Not for a commercial piece: Jamendo's free API, and Google Flow Music, which
  has published no commercial terms.
