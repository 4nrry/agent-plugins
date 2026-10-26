# Image tools

Checked against the vendors' docs on 2026-10-26; model names, prices and
quotas change monthly, so check again before a paid run. Each script checks
that the file was written. Commands run from the skill's directory.

| Tool | Script | Good for | Notes |
|---|---|---|---|
| Grok Imagine, through Grok Build (`grok`) | `scripts/grok-image.sh "<prompt>" out.png` | exploring directions fast | sober documentary look; no negative prompt field |
| Gemini image, through Antigravity (`agy`) | `scripts/agy-image.sh "<prompt>" out.png` | the final still | richer light and detail, more "AI look" |
| Gemini image API | `scripts/nano.py <model> "<prompt>" -o out.png [--image in.png]` | batches, or when agy's quota is out | `gemini-nano-banana-2.1` (newest), `gemini-3.1-flash-image` (cheaper), `gemini-3-pro-image` (edits; ask gently, it overdoes changes) |
| Grok Imagine API (`grok-imagine-image-2.0`, `-quality`) | none bundled | batches billed per image | needs an xAI API key, not the SuperGrok login |
| Z-Image Turbo, local | `image-retouching` skill, `comfy-run.py generate` | offline, Apache-2.0 weights | 8 GB GPU |

## Setup

Only needed when a tool fails. Every billing step is the user's.

**agy (Antigravity CLI).** Needs a Google AI Pro or Ultra subscription, with
`agy` installed and logged in. Headless:
`agy -p "..." --output-format json --dangerously-skip-permissions --sandbox`;
the image tool is `generate_image`. Run the official binary only: reusing
agy's login token in another tool breaks the terms.

**grok (Grok Build).** Needs a SuperGrok subscription, with `grok` installed
and logged in. Grok Build's command is `/imagine`; headless,
`grok -p "..." --cwd DIR --always-approve --output-format json` and the script
asks the agent for an image.

**Gemini API.** `GEMINI_API_KEY` from a project linked to a billing account,
kept in the secrets manager and injected only into the process. New accounts
are prepaid: at zero balance the API answers HTTP 402, even with Cloud
credits applied. The `video-generation` skill's `references/tools.md` has the
full billing setup.
