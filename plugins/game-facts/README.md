# game-facts

Pins the installed game's version before the agent answers from training
memory, so the user never has to type the version into the prompt.

```
/plugin install game-facts@4nrry
```

| Component | Path | Does |
|---|---|---|
| Hook | `hooks/inject-game-version.sh` | `UserPromptSubmit`: when the prompt names an installed Steam game, injects appid, buildid, update date and the patch-notes URL. Fails open |
| Skill | `skills/game-versions/SKILL.md` | Read the disk, route the question, changelog first, weigh sources |
| References | `skills/game-versions/references/` | Source order and traps (`sources.md`), games outside Steam (`launchers.md`) |
| Detector | `skills/game-versions/scripts/steam_games.py` | Parses appmanifests and matches names as whole phrases; `--self-test`, `--json`, `--match-stdin` |

The hook builds the patch-notes URL but never fetches it: it runs on every
prompt. Names match as whole phrases between non-alphanumeric boundaries, so
"It Takes Two" does not fire on "takes two hours".

Only Steam is parsed. Heroic, flatpak, RetroDECK and Lutris are documented as
places to look, with formats marked unverified.

**Evidence:** the source rules come from a one-game, one-day survey of 80
sources, recorded as notes in
[`bench/plugins/game-facts/results/2026-09-07-source-survey-CLAIMS.md`](../../bench/plugins/game-facts/results/2026-09-07-source-survey-CLAIMS.md).
How often the hook fires, and whether it changes answers, is not measured.
