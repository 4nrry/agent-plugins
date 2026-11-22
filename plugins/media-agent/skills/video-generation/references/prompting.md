# Video prompting patterns across models

Model-specific syntax, blocking before camera, and reference role isolation for AI video generation. Distilled from `4nrry/video-prompting-skill` (Apache-2.0), `4nrry/seedance-2.0` (MIT), `4nrry/DirectorSKILL` (MIT), and `4nrry/ai-filmmaking-camera-control-seedance-2-5` (MIT).

## Contents

- [Global rules](#global-rules)
- [Asset handoff chain](#asset-handoff-chain)
- [Reference role isolation and continuations](#reference-role-isolation-and-continuations)
- [Blocking and staging before camera](#blocking-and-staging-before-camera)
- [3D pill-pipeline camera control](#3d-pill-pipeline-camera-control)
- [Model syntax cheatsheet](#model-syntax-cheatsheet)

## Global rules

- **Keep metadata out of the prompt text.** Never write the model name, model version, duration (`6s`), aspect ratio (`9:16`), resolution (`720p`), or API flags inside the prompt string unless a model's structured schema explicitly requires timestamps. Pass those as external parameters only.
- **Image-to-video anchors visuals in the still.** When passing `first_frame`, do not waste tokens re-describing the static room, clothing, or props already locked in the image unless one detail must change; spend the prompt budget on motion, camera move, acting beats, and audio.
- **Describe concrete exclusions positively where possible.** When a model has no negative prompt field, describe clean visual state plus explicit exclusions (for example: `clean deep-teal water, no on-screen text, no subtitles, no floating letters`).

## Asset handoff chain

Follow one directional chain before generating video:

1. **Character sheet / turnaround:** lock proportions, limb count, face markers, and palette once.
2. **Star graph of scene stills:** generate the anchor still (`G1`: main set + cast) and derive reverse angles, two-shots, split openings, and prop shots by image-editing from `G1` plus the character sheet — never from a video tail frame.
3. **Image-to-video shot prompt:** animate each approved scene still via `first_frame`.

## Reference role isolation and continuations

Multi-reference models copy unintended traits (room lighting, performer face, costume, logos) unless each asset's boundary is explicit:

- **Role isolation (`r2v-role-isolation`):** state both what each reference controls AND what to ignore.
  - Pattern: `@Image1 locks character identity and wardrobe only. @Video1 controls camera trajectory and rhythm only; ignore its performer, room, logo, and outfit. @Audio1 sets tempo only; do not copy its voice identity.`
- **Observed-end-state continuation:** when extending or picking up after an accepted clip, describe the **observed** final frame rather than what the original script assumed happened.
  - Example: if the script expected the character at the door but the accepted clip ended two steps short, start with `still two steps from the doorway, mid-stride; finish those two steps before reaching the handle` rather than assuming they are already at the door.

## Blocking and staging before camera

Blocking is the first directorial decision; camera follows bodies. In AI video, staging survives generation far more reliably than motion verbs because geometry lives inside the `first_frame` still.

### Proxemics (distance creates subtext)

| Zone | Distance | Reads as | Camera consequence |
|---|---|---|---|
| Intimate | `0–0.45 m` | Secret, tension, closeness | Frontal two-shots overlap heads; go near-profile or tight over-the-shoulder. |
| Personal | `0.45–1.2 m` | Friendship, conspiracy, equals | Natural two-shot (`40–50 mm` equiv. at `~1.8 m`) with air between faces. |
| Social | `1.2–3.6 m` | Work, transaction, formality | Needs wide framing (`28–35 mm`) or barrier object (desk/table) between subjects. |
| Public | `3.6 m+` | Performance, isolation, address | Both figures read small unless foregrounded for scale contrast. |

- **Three-beat acting:** write physical beats as `anticipation -> concrete gesture -> reaction/settle`, specifying exact hands/limbs and keeping listening characters mouth-closed in frame.
- **Stage depth in 3 planes:** foreground anchor (shoulder edge, prop on desk), midground speaker (`>= 1/3` frame height, clean silhouette), background set cues.

## 3D pill-pipeline camera control

When a video model ignores complex text camera directions (orbits, crane sweeps, whip pans, FPV paths), drive it with a clean 3D layout clip where characters/props are **striped capsules (pills)**:

- A reference video carries two signals: **camera/framing/timing** and **surface appearance**. Striped pills give the model exact scale, facing, position, and camera path while keeping looks coarse so text prompts and character image refs paint the real world cleanly.
- Useful for `reference_to_video` models that accept a motion/camera reference video alongside character image references.

## Model syntax cheatsheet

| Model | Dialogue & audio syntax | Key parameters & quirks |
|---|---|---|
| **Grok Imagine** | Colon without quotes (`Character speaks in <voice>: line`) so words do not render in scene; join internal clauses with commas to avoid ~0.7 s dead pauses | `4096`-char prompt limit; pass `first_frame` (`9:16` / `16:9`, up to `10 s` ref-to-video); avoid quoted speech and multi-panel sheets |
| **Veo 3 / 3.1** | `[Cinematography] + [Subject] + [Action] + [Context] + [Style]`; explicit `SFX:` and `Ambient noise:` lines | Native joint audio-video; keep one clear move and 2–4 action beats per clip |
| **Seedance 2.0 / 2.5** | Indexed `@Image1`, `@Video1`, `@Audio1` with explicit role isolation; supports `4–30 s` continuous or phased shots | Strong camera/motion adherence with 3D pill clips or first/last frame constraints |
| **LTX-2.3 / 2.5** | Chronological prose (`camera + subject + action + lighting + audio`); supports `first/last` frame and LoRA styles | Keep prompt duration aligned externally (`(frames-1) % 8 == 0`, 24 fps default) |
| **MiniMax H3** | `I2VA` / `FL2VA` / `T2VA` headers with explicit `0.00s` frame binding; `integrated_multimodal_description` | Supports timestamped multi-beat action and separate `overall_soundscape` |
| **Kling 4.0** | `[REFERENCE ROLES]` + `[TIMED SHOTS]` (`0-3s`, `3-6s`) for match cuts and multi-reference dialogue | Lock object screen coordinates (`% width/height`) across cuts for clean match cuts |
