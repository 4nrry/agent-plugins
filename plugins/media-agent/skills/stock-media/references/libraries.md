# Stock libraries

Licenses checked against each service's terms on 2026-10-26.

| Source | Has | License | Trap |
|---|---|---|---|
| Openverse (no key) | CC audio and images | per item; `license_type=commercial` filters | the filter trusts declared metadata |
| Freesound (key) | SFX | per item; filter `license:"Creative Commons 0"` | original downloads need OAuth2; the HQ mp3 preview does not and is enough for SFX |
| Pexels (key) | photos and video | Pexels License: commercial, credit optional | the CDN returns 403 without a `User-Agent`; pick the widest of `video_files` |
| Pixabay (key) | photos and video | Pixabay Content License: commercial, no standalone resale | no music through the API; the terms require caching responses for 24 h, which the script does under the user cache directory |
| Jamendo | music | free API is non-commercial | company video needs a paid license |
| Google Flow Music (Lyria 3.5) | generated music | no commercial terms published as of 2026-10-26 | not for a commercial piece |
| YouTube Audio Library | music | for videos you create; no standalone distribution | Creator Music tracks are YouTube-only: check which kind a track is |
