# One-time setup

Only needed when `grok`, `agy` or Veo fails. Every billing step is the user's.

## agy (Antigravity CLI)

- Needs a Google AI Pro or Ultra subscription, with `agy` installed and logged in.
- Headless: `agy -p "..." --output-format json --dangerously-skip-permissions --sandbox`.
  The image tool is `generate_image`; there is no video tool.
- Terms: running the official binary from a script or another agent, on the user's
  own machine and for the user only, was described as permitted on the official
  forum (by a poster who does not appear to be a Google employee). Reusing agy's
  login in another tool (MCPs that call the endpoint with its token) is
  prohibited by the terms.

## grok (Grok Build)

- Needs a SuperGrok subscription, with `grok` installed and logged in.
- Headless: `grok -p "..." --cwd DIR --always-approve --output-format json`.
  Observed tools: `image_gen` and `reference_to_video`.
- With ZDR privacy on, video returns "Video generation tools are unavailable
  under zero data retention (ZDR)". Either the user turns ZDR off (`/privacy`) or
  configures their own S3-compatible bucket:
  `S3_ENDPOINT=... S3_BUCKET=... scripts/grok-zdr-bucket.sh`, which writes
  `[tools.zdr_video_output_s3]` to `~/.grok/managed_config.toml`. An R2 key can
  only be created in the Cloudflare dashboard.

## Veo (Gemini API with Google credits)

1. Google Developer Program benefits active through the AI Pro subscription; apply
   each monthly credit (US$ 10) to a billing account, one by one.
2. A project linked to that billing account, and an API key created in AI Studio
   under that project. Keep `GEMINI_API_KEY` in the secrets manager and inject it
   only into the process.
3. **Prepaid balance above zero in AI Studio.** Without it: `HTTP 402: Your
   prepayment credits are depleted`, even with Cloud credits applied. With a
   balance, credits are spent first. A new account is prepaid, with no way back.
4. Spend cap: a budget with Spend cap enforcement on the project's "Gemini API"
   service. It measures list price and ignores credits; a monthly cap below the
   monthly credit keeps the card out of it. It is not instantaneous.

Models: `veo-3.1-generate-preview`, `veo-3.1-fast-generate-preview`,
`veo-3.1-lite-generate-preview`. To test the key and balance without spending Veo,
make a 1-token text call; `gemini-2.5-*` returns 404 for new users.
