# Batch 2026-10-28-sinalpublico — claims

**Notes, not run records.** Source of the `3d-scenes` and `sourced-video`
skills (media-agent 0.14.0): the owner's private channel repository
(Sinal Público, short vertical videos about sourced real events, low-poly 3D
in Blender, VHS post), built 2026-10-25 to 28 without media-agent loaded.
Figures marked *repo* were measured there and are copied from its docs and
code; figures marked *here* were re-run on 2026-10-28 on the same machine
(RTX 4070 Laptop 8 GB beside an Intel Arc, Blender 5.2.0). n=1 per item.

**Blender**
- *here*: `blender -b -P bad.py` exits 0 after an uncaught `RuntimeError`;
  with `--python-exit-code 1` it exits 1.
- *here*: `scene_kit.py --demo` on the CC0 Quaternius `animated-human.glb`:
  three figures at face 0, -π/2 and π render front, profile and back, each
  1.900 m with feet at z 0, in `XYZ` rotation mode. Action Idle frame 10 reads
  as walking; Death frame 0 is a neutral stand.
- *here*: 24 `final` frames (540×960, 8 TAA, 64 volume samples, 2 px volume
  tiles) of that three-figure scene in 3 s; 2 px tiles remove most of the
  grid that 8 px tiles leave in the fogged spot cone.
- *repo*: rotation written to `rotation_euler` on a glTF root is ignored
  (quaternion mode); the rest pose of that glb is a run; applying the armature
  alone left the mesh in the bind pose.
- *repo*: Blender 4.2.23 EEVEE Next, per frame after the first: `relogio_gancho`
  4.44 s legacy (16 TAA), 2.54 s final (8 TAA), 0.43 s preview (270×480,
  4 TAA); `ponto` (five figures) 5.65 / 3.19 / 0.52 s. Lowering volume samples
  below 64, or turning EEVEE bloom off, gridded the spot cone.
- *repo*: EEVEE on the NVIDIA card via PRIME offload was about 4× faster than
  on the Intel Arc.
- *repo*: `h264_nvenc` constqp 20 matched x264 crf 17 on 12 s (PSNR 30.52 vs
  30.52 dB, SSIM 0.9508 vs 0.9510, +4 % size) in 3.3 s against 12.3 s.

**Scripts** (*here*)
- `check_motion.py`: exit 0 on the 24 moving demo frames (smallest change
  0.073); exit 1 on a sequence with three identical frames; exit 1 on an empty
  folder.
- `check_sources.py`: exit 0 on the example spec in `references/spec.md`;
  on a copy with five planted faults (a fact with one opened source, an
  unknown source id, a forbidden phrase on screen, 8 s against 5 s for two
  sides, a synthetic real person) it listed six problems and exited 1.
- `sfx-synth.py`: all ten presets write 48 kHz mono at -3.0 dBFS peak; the
  same seed gives a byte-identical file.

**Activation** (*here*; `claude -p` 2.1.312, sonnet, `--plugin-dir` on the
branch, up to 4 turns, one run per prompt; 24 prompts written by a subagent
that saw only one-line skill areas)
- First descriptions: 3d-scenes 3/7, sourced-video 3/7, neighbours
  (3d-turntable, video-composition, voice, audio) 8/8, negatives 2/2. Misses
  were answered from memory, or spent the turns looking for files.
- After rewording both descriptions toward those misses: 3d-scenes 6/7,
  sourced-video 7/7; neighbours and negatives re-run 6/6. These are the same
  prompts the rewording targeted, so the second score is optimistic. The
  remaining miss (jagged shadows and blown highlights in EEVEE) is outside
  the skill.

**Voice** (*repo*)
- Grok Imagine `reference_to_video`, used for its narrator voice, refused the
  line naming a party and a candidate (`imagine:content-moderated`); the
  series moved its narration to another TTS without rewording.
