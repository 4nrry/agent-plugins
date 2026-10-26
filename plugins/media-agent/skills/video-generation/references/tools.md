# Video tools

Checked against the vendors' docs on 2026-10-26; model names, prices and
quotas change monthly, so check again before a paid run. Commands run from the
skill's directory.

A subscription route spends the plan's quota and nothing more; an API-key
route bills every call to that key. Prefer the subscription routes when the
key's budget belongs to something else.

| Tool | Billed to | Script | Good for | Notes |
|---|---|---|---|---|
| Gemini Omni (`gemini-omni-1.1-flash`), Gemini API | Gemini API key, per second | `python3 scripts/omni.py "<motion>" -o shot.mp4 --image still.png` | shots from a still, between a first and a last frame (`--last`), or of a subject from references (`--ref`); extending a clip (up to 40 s in total) and editing it in turns, through the API only | 360p or 720p native; 1080p and 4k are upscaled by Google; 16:9 or 9:16; no negative prompt and no duration setting: clips come back at 10 s, 24 fps, with an audio track (trim in the edit) |
| Grok Imagine video, through Grok Build | Grok subscription | `scripts/grok-video.sh "<motion>" out.mp4 --image still.png` | backgrounds, small cards, Reels backdrops | 480p by default, `--res 720p` at most: on the subscription, both Grok Build's video tools and Hermes's refuse 1080p ("resolution_name must be one of: 480p, 720p"), while the web app makes it ([grok-web.md](grok-web.md)); 6 s clips with audio |
| Google Flow (web), Omni Flash and Veo 3.1 | Google AI Pro/Ultra credits | a browser, [flow.md](flow.md) | Omni and Veo without an API key: from a still, first and last frame, extend and edit in the app | 360p 8 s Omni costs 6 credits; no API, so a browser agent drives it with the user signed in |
| Grok Imagine on grok.com (web) | Grok subscription | a browser, [grok-web.md](grok-web.md) | native 1080p on the subscription, 6, 10 or 15 s, first and last frame, loops | 1080p came back as 1904x1072; no API, so a browser agent drives it with the user signed in |
| Grok Imagine API (`grok-imagine-video-1.5`, `-1.5-lite`) | xAI API key, per second (billed apart from the Grok subscription) | none bundled | native 1080p, 1–15 s, reference images | priced per second; needs an xAI API key |
| Veo 3.1 GA (`veo-3.1-generate-001`, `-fast-`) | Google Cloud billing (Vertex) | none bundled | premium shots | only on Google's enterprise platform (Vertex), us-central1 |
| ElevenLabs canvas (MCP) | ElevenLabs plan credits | `audio` skill | upscaling a clip (Topaz) | video models there cost a large share of a month's credits per clip |

`--last` and `--ref` follow the Omni docs (two images for first and last
frame; task `reference_to_video` for references) and have not been run yet:
the first live call hit the project's spend cap.

The Veo 3.1 preview in the Gemini API, which the old `veo.py` used, was shut
down on 2026-10-22.

## Setup

Every billing step is the user's.

**Gemini API (Omni).**

1. A project linked to a billing account, and an API key created in AI Studio
   under that project. Keep `GEMINI_API_KEY` in the secrets manager.
2. Google AI Pro includes monthly Google Cloud credits through the Developer
   Program; apply each one to the billing account.
3. **Prepaid balance above zero in AI Studio.** New accounts are prepaid; at
   zero the API answers HTTP 402, even with Cloud credits applied.
4. A budget with spend-cap enforcement on the project's Gemini API service. It
   measures list price and ignores credits, and it is not instantaneous.

To test the key and balance without spending on video, make a 1-token text
call.

**Grok video.** Same `grok` login as for images (Grok Build's `/imagine-video`
command; headless, the script asks the agent for it). With zero data retention
(ZDR) on, the CLI returned "Video generation tools are unavailable under zero
data retention". Either the user turns ZDR off (`/privacy`), or points Grok at
their own S3-compatible bucket: `S3_ENDPOINT=... S3_BUCKET=...
scripts/grok-zdr-bucket.sh` writes `[tools.zdr_video_output_s3]` to
`~/.grok/managed_config.toml`. An R2 key can only be created in the Cloudflare
dashboard.
