# Stock libraries

Licenses checked against each service's terms on 2026-10-26.

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

| Source | Has | License | Trap |
|---|---|---|---|
| Openverse (no key) | CC audio and images | per item; `license_type=commercial` filters | the filter trusts declared metadata |
| Freesound (key) | SFX | per item; filter `license:"Creative Commons 0"` | original downloads need OAuth2; the HQ mp3 preview does not and is enough for SFX |
| Pexels (key) | photos and video | Pexels License: commercial, credit optional | the CDN returns 403 without a `User-Agent`; pick the widest of `video_files` |
| Pixabay (key) | photos and video | Pixabay Content License: commercial, no standalone resale | no music through the API; the terms require caching responses for 24 h |
| Jamendo | music | free API is non-commercial | company video needs a paid license |
| YouTube Audio Library | music | for videos you create; no standalone distribution | Creator Music tracks are YouTube-only: check which kind a track is |
