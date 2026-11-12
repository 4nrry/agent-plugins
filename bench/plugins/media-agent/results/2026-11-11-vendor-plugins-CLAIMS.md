# Batch 2026-11-11-vendor-plugins — claims

**Notes, not run records.** Why media-agent 0.21.0 drops the HTML capture
written by hand, makes the HyperFrames CLI a dependency of the video project,
keeps telemetry off, and says how the skill behaves beside HeyGen's and
Remotion's own plugins. These were the owner's decisions after 0.20.0; the
numbers below are what was measured while carrying them out.

**Installing the two plugins.** 2026-11-11, Claude Code 2.1.322, user scope,
`git-lfs` not installed.

| | `hyperframes@hyperframes` 0.9.35 | `remotion@remotion` 4.0.543 |
|---|---|---|
| Marketplace clone | 408 MB, 6.2 s (the whole repository; its Git LFS files stay pointers, "at least 84" by the installer's message) | 3.3 MB, 2.0 s |
| Plugin cache | 338 MB | 2.9 MB |
| Skills, agents, hooks, MCP servers | 9, 0, 0, 0 | 13, 0, 0, 0 |
| Always-on context, as `claude plugin details` projects it | about 996 tokens | about 345 tokens |
| Largest skill when invoked, same source | `hyperframes-cli`, about 2.8k tokens | `remotion-interactivity`, about 5.2k tokens |

**Read in the installed HyperFrames plugin, not run.**

- `media-use/SKILL.md`: before any request that needs a HeyGen model or the
  catalog it has the agent check `auth status` and ask the person to run
  `auth login`; "Use local tools only when the person asks, not as a
  fallback"; "no cheaper or free swaps, no dropped items, unless asked to save
  cost. Don't volunteer prices, estimates or usage".
- Its voice reference lists ElevenLabs second in an automatic provider order,
  read from `ELEVENLABS_API_KEY`; Gemini is used only when asked for, from
  `GEMINI_API_KEY` or `GOOGLE_API_KEY`. None of those variables was set in the
  session that read this.
- `hyperframes/references/plugin-installation.md`: inside a plugin every
  `npx hyperframes` becomes `node <plugin root>/skills/hyperframes/scripts/plugin-cli.mjs`,
  which takes the version from the plugin manifest and starts npm in the home
  folder so the project's `node_modules` cannot choose the CLI; the agent does
  not update the plugin.

**Run once.** In a HyperFrames project, the launcher with `--version` printed
0.9.35 in 0.6 s (the CLI was already in the npx cache), `telemetry status`
printed "disabled", and `info --json` read the project.

**Read in the installed Remotion plugin, not run.** `remotion-render/SKILL.md`:
"If the user qualifies for the free license, pass `free-license` instead" of a
company key. Remotion's telemetry page (tag v4.0.543) says server-side
rendering reports "only when a license key is set", and the License FAQ says
"Telemetry in server-side rendering remains voluntary for Free License users";
the 5.0 migration page, under a heading about Company License customers, says
to pass `free-license` when eligible for the free license. The plugin's
app-building skill passes the same key to the render APIs.

**The capture written by hand.** `references/html-capture.md` is removed. It
was never measured in this repository: no record under `bench/` covers it.
What it described (a `seek(t)` page, one PNG per frame, `ffmpeg` encoding) is
what HyperFrames does, with a linter, a layout check and an audio mix.

**Not measured.** No video was made through either vendor's skills, so how a
model weighs their text against this plugin's when both are loaded is
unknown: the precedence rule in `SKILL.md` is an instruction, not a result.
Whether the HeyGen plugin's 9 descriptions or Remotion's 13 change which skill
a video request loads. The plugins' update flow. A HeyGen sign-in, any credit
and any cloud render: none was used.

**Why `telemetry disable` is back.** 0.20.0 left the lasting setting to the
user and set only the environment variable. The owner then decided telemetry
is always off, so 0.21.0 runs it once per machine as well. The CLI's docs say
any way of turning telemetry off takes the install out of canary rollouts, not
that command alone.

**From the cold review.** A subagent compared the diff with the installed
plugins, both tags and Kinocut's source. Confirmed and fixed:

- `npm install --save-dev hyperframes@0.9.35` wrote `"^0.9.35"` (seen in the
  test project of the render record), so Setup now passes `--save-exact`.
- HeyGen's rule against rewriting a project's dependency files to match the
  plugin contradicted "keep the dependency at the plugin's version": a
  mismatch is now reported and changed only with the user's yes, and the
  launcher is named as the way to run the CLI while the plugin is installed.
- `init` writes no dependency, so an existing project needed its own rule.
- "Run these only when the user asks" could be read as the local render.
- Uploads were missing from the two short statements of the precedence rule.
- HeyGen's CLI skill makes `cloud render` the final render on a paid plan, and
  its main skill runs `usage --json`, which reads the agent's own login.
- The Git LFS count did not reproduce; it is now quoted as the installer's.

Nothing was rejected. The launcher's `--version` and `telemetry status` runs
above were not repeated by the reviewer.
